---
layout: default
title: Azure Local with Everpure FlashArray Quick Start Guide for Disaggregated Deployments (FC)
---

# Azure Local with Everpure FlashArray Quick Start Guide for Disaggregated Deployments

---

{% include quickstart/disclaimer.md %}

---

This guide provides a high-level workflow for integrating the Everpure FlashArray as the **only** block storage for a **disaggregated** Azure Local (formerly Azure Stack HCI) deployment. In a disaggregated deployment there is no local Storage Spaces Direct (S2D) — compute runs on the Azure Local nodes while all cluster storage is served from the FlashArray over Fibre Channel. This combines the cloud-integrated benefits of Azure Local with the high-performance, data-reduced storage of FlashArray, and lets compute and storage scale independently.

> **This document is based heavliy on the official Microsoft documentation.**  [Deploy Azure Local using the Azure portal for disaggregated deployments](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated)

> **Looking for iSCSI instead?** See the [Disaggregated iSCSI guide](../iscsi/QUICKSTART.md). **Looking for a hyperconverged (S2D + FlashArray) cluster?** See the [Hyperconverged FC guide](../../hyperconverged/fc/QUICKSTART.md).

## Prerequisites to Using the Quick Start Guide

Before you begin, ensure that the following requirements are met:

### Everpure FlashArray

- A deployed and configured Everpure FlashArray.
- Fibre Channel (FC) must be enabled and configured on the array, with active zoning and connectivity established between the FlashArray and **all** Azure Local nodes.
- See the [SAN Guidelines for Maximizing FlashArray Performance](https://support.everpuredata.com/bundle/m_microsoft_platform_guide).
- **Minimum Recommended Purity Version: 6.5.3**

### Azure Local Deployment (Base)

Unlike a hyperconverged cluster, a **disaggregated cluster is deployed *onto* the FlashArray** — so the FlashArray host/volume setup and node MPIO configuration happen **before and during** the Azure Local deployment, not after.

- Machines from the [Azure Local Catalog](https://aka.ms/AzureStackHCICatalog) racked, with the OS preinstalled and **registered with Azure Arc** (deployment permissions assigned). The cluster itself is created as part of this guide.
- Each node requires its own **local OS boot media** — only the cluster *data/infrastructure* storage comes from the SAN.
- **Minimum Azure Local Version: 2604** (disaggregated SAN deployment is generally available in 2604).
- A disaggregated instance supports **1 to 64 machines**. **Rack-aware** clusters are *not* supported with disaggregated deployments.

> **Important — present the deployment LUNs before you run the wizard.** The disaggregated deployment wizard requires you to select two existing SAN LUNs: an **infrastructure** volume and a **cluster performance-history** volume. Both must already be zoned and presented to all nodes when you start the wizard. At the time of writing (Azure Local **2604**) the minimums are **250 GB** (infrastructure) and **20 GB** (performance history), but Microsoft has revised these between releases — always confirm the current values in [Microsoft's Azure Local system requirements](https://learn.microsoft.com/en-us/azure/azure-local/concepts/system-requirements-23h2?tabs=azure-public#machine-and-storage-requirements) before sizing.

## Workflow Overview

At a high level, the disaggregated Azure Local integration with FlashArray includes the following phases:

1. **Configure the Azure Local nodes** — install and tune MPIO (before deployment).
2. **Everpure FlashArray setup** — create hosts, a host group, and the infrastructure + performance-history volumes (before deployment).
3. **Deploy the disaggregated Azure Local cluster** — run the portal wizard with **Storage = SAN** and select the two LUNs.
4. **Azure Local cluster storage configuration** — add day-2 workload volumes as Cluster Shared Volumes (CSVs).

While graphical interfaces such as Windows Admin Center or Failover Cluster Manager are available for setup and administration, **PowerShell is the recommended method** for the initial setup. It provides precision, consistency across nodes, and scriptability. This guide focuses on PowerShell-based execution, supplemented by GUI screenshots to illustrate key validation points.

> For the best experience, use **PowerShell 7.6 or later** when performing the steps in this guide.

> **Note on naming:** Azure does **not** support underscores (`_`) for these resource types. While the FlashArray is flexible with naming, use **hyphens (`-`)** for your Host, Host Group, and Volume names to remain fully compatible with Azure Arc-enabled services.

---

## Phase 1: Configure the Azure Local Nodes

Multipath I/O (MPIO) is a critical configuration requirement for Azure Local nodes. It provides hardware resiliency by establishing redundant physical paths between the node and the storage array, and facilitates performance load balancing by distributing I/O traffic across all active paths.

### 1.1 HBA Driver and Firmware

Before software configuration, the physical Host Bus Adapters (HBAs) must run vendor-specific driver/firmware versions — default drivers are insufficient for production.

- All HBAs (e.g., Marvell/QLogic or Broadcom/Emulex) must run driver and firmware versions found in the [Windows Server Catalog for Azure Local](https://www.windowsservercatalog.com/).
- The HBA must also be supported by the server vendor for the specific server model in use.
- Install and confirm that the latest validated drivers are running on the HBAs.

### 1.2 Enable the MPIO Feature

The MPIO framework must be installed and active on **every** node in the cluster.

> **Attention:** To remotely run PowerShell on an Azure Local node, enable Remote Management on the target node using the **SConfig** utility (Option 4) and ensure the firewall allows WinRM traffic.

> **Note:** All MPIO setup commands in this section must be executed individually on **each** Azure Local node.

> **Note:** To run remotely from a workstation first enter a new remote session:

```powershell
# Open a remote session to a node (run from your management workstation)
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
```
> **Note:** Commands from here on should either be run in the remote session or locally on the hypervisor node.

Azure Local **2604 and later enables MPIO by default**, so this step is primarily a verification. If MPIO is not enabled (possible on earlier builds), enabling it requires a reboot.

```powershell
# Check first — do not enable blindly on a running node
$mpio = Get-WindowsOptionalFeature -Online -FeatureName MultipathIO
$mpio | Select-Object FeatureName, State

# Only if State is 'Disabled' — -NoRestart avoids an interactive reboot prompt
if ($mpio.State -ne 'Enabled') {
    Enable-WindowsOptionalFeature -Online -FeatureName MultipathIO -NoRestart
}
```

### 1.3 Claim FlashArray as an MPIO Target

By default the OS does not claim external arrays for multipathing. Register the FlashArray hardware IDs with the Microsoft Device Specific Module (MSDSM).

```powershell
New-MSDSMSupportedHw -VendorId "PURE" -ProductId "FlashArray"
```

This registers Everpure devices as MPIO-capable. Modern PowerShell automatically handles the character padding for these IDs.

Optionally, remove the default placeholder entry so MSDSM does **not** automatically claim unrelated devices. Use the exact IDs rather than a wildcard so the removal cannot match a real vendor entry:

```powershell
Remove-MSDSMSupportedHW -VendorId 'Vendor 8' -ProductId 'Product 16' -Confirm:$false
```

> **Note:** A **reboot is required** after these changes for MSDSM to begin claiming the FlashArray.

### 1.4 Configure MPIO Best Practices

Set the global load-balancing policy according to FlashArray standards:

- **10 or fewer paths:** Round Robin (RR).
- **More than 10 paths:** Least Queue Depth (LQD).

```powershell
Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy RR    # 10 or fewer paths
# Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy LQD  # more than 10 paths
```

> For a deeper dive, see the [Setting the MPIO Policy](https://support.everpuredata.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy) KB. Round Robin with Subset (RRWS) is also an option for high path counts but must be set per-volume (it cannot be a global default).

### 1.5 Configure Path Verification and Timeouts

Tuning MPIO timers prevents premature path failovers and lets the system recover gracefully from momentary fabric hiccups.

```powershell
Set-MPIOSetting -NewPathRecoveryInterval 20 -CustomPathRecovery Enabled `
    -NewPDORemovePeriod 20 -NewDiskTimeout 60 `
    -NewPathVerificationState Enabled -NewPathVerificationPeriod 30
```

`NewPDORemovePeriod` determines how long the OS waits for a failed path to recover before the device is removed.

> **Note:** These are the Everpure FlashArray-specific overrides documented by Microsoft in [Enable External Storage on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage). Everpure Data's general Windows Server guidance uses `-NewPDORemovePeriod 30`, which holds a failed path slightly longer so MPIO can complete a path-level failover before the Cluster Storage Service sees the disk as "gone" and prematurely triggers a node failover. If you observe premature node failovers on path loss, raise it to `30` — consistently on **every** node.

> **Note:** Workloads with specific latency requirements or complex fabrics may require additional tuning.

### 1.6 Verify Azure Node Readiness

Before moving to FlashArray preparation, verify the staging and collect the WWNs.

```powershell
# Confirm timers
Get-MPIOSetting

# Confirm global policy returns RR (or LQD)
Get-MSDSMGlobalDefaultLoadBalancePolicy

# Confirm PURE / FlashArray appear in the supported hardware list
Get-MSDSMSupportedHw

# Record the HBA World Wide Names (WWNs) for each node — needed in Phase 2
Get-InitiatorPort
```
### 1.7 Repeat for all Azure Local Nodes

Repeat Phase 1 steps for each node.

---

## Phase 2: Everpure FlashArray Setup

With the nodes prepared and their WWNs collected, provision the storage on the FlashArray. This guide uses the **Everpure PowerShell SDK v2** for repeatability.  The GUI may be used for these actions as well.  See the [FlashArray Admin Guide](https://support.everpuredata.com/r/flasharray-admin-and-cli-reference-guides/flasharray-admin-and-cli-reference-guides).

> **Note:** This guide assumes the Fibre Channel zoning has already been completed and is outside the scope of this document.  Consult your switch provider for additional information regarding this.

> **Run these from a management workstation — not from an Azure Local node or a remote PS session to an Azure Local node** (the nodes are security-locked). 

```powershell
# Install and import the Everpure PowerShell SDK v2
Install-Module -Name PureStoragePowerShellSDK2 -Force -AllowClobber
Import-Module -Name PureStoragePowerShellSDK2

# Connect to the FlashArray management VIP
$Conn = Connect-PFA2Array -Endpoint "<FlashArray_Management_VIP>" -Credential (Get-Credential) -IgnoreCertificateError
```

### 2.1 Create Host Objects

Create a host object for **every** node, mapping **all** of its WWNs (from Phase 1.6). `-Wwns` takes an array — pass every WWPN the node reports, not just one.

```powershell
# One host object per node, each with all of that node's WWPNs
New-Pfa2Host -Array $Conn -Name "<Node_1_Name>" -Wwns "<Node_1_WWPN_A>", "<Node_1_WWPN_B>"
New-Pfa2Host -Array $Conn -Name "<Node_2_Name>" -Wwns "<Node_2_WWPN_A>", "<Node_2_WWPN_B>"

# Or drive it from a hashtable of node name -> WWPN list
$NodeWwpns = @{
    "<Node_1_Name>" = @("<Node_1_WWPN_A>", "<Node_1_WWPN_B>")
    "<Node_2_Name>" = @("<Node_2_WWPN_A>", "<Node_2_WWPN_B>")
}
foreach ($node in $NodeWwpns.Keys) {
    New-Pfa2Host -Array $Conn -Name $node -Wwns $NodeWwpns[$node]
}
```

### 2.2 Create and Configure the Host Group

In a clustered environment, manage hosts via a Host Group so all nodes have consistent, simultaneous access to the same volumes — a requirement for CSVs.

```powershell
# One host group for the whole cluster, e.g. Azure-Local-Cluster-01
New-Pfa2HostGroup -Array $Conn -Name "<Host_Group_Name>"

# Add all node host objects to the group
New-Pfa2HostGroupHost -Array $Conn -GroupName "<Host_Group_Name>" -MemberName "<Node_1_Name>", "<Node_2_Name>"
```

### 2.3 Create the Deployment Volumes

A disaggregated deployment requires **two** volumes to exist before the wizard runs. The minimum sizes below are current at the time of writing (Azure Local **2604**); Microsoft has changed them between releases, so confirm against the [Azure Local system requirements](https://learn.microsoft.com/en-us/azure/azure-local/concepts/system-requirements-23h2?tabs=azure-public#machine-and-storage-requirements) and size the infrastructure volume for your cluster's needs.

| Volume | Minimum size (2604) | Purpose |
| --- | --- | --- |
| Infrastructure volume | **250 GB** | Cluster infrastructure storage |
| Cluster performance-history volume | **20 GB** | Performance history |

```powershell
# Infrastructure volume (>= 250 GB)
New-Pfa2Volume -Array $Conn -Name "<Cluster>-infra" -Provisioned 250GB

# Cluster performance-history volume (>= 20 GB)
New-Pfa2Volume -Array $Conn -Name "<Cluster>-perfhistory" -Provisioned 20GB
```

> Workload volumes are created later in Phase 4.

### 2.4 Connect the Volumes to the Host Group

Mapping to the Host Group (not individual hosts) makes the storage visible to all nodes with **consistent LUN IDs**.

```powershell
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-infra"       -HostGroupName "<Host_Group_Name>"
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-perfhistory" -HostGroupName "<Host_Group_Name>"
```

The FlashArray is now presenting the infrastructure and performance-history LUNs to all nodes, ready for the deployment wizard.

---

## Phase 3: Deploy the Disaggregated Azure Local Cluster

Run the deployment from the Azure portal. The selections below differ from a standard S2D (hyperconverged) deployment.

> Full reference: [Deploy Azure Local using the Azure portal for disaggregated deployments](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated).

### 3.1 Basics — choose SAN storage

On the **Basics** tab, set **Storage options** to **Storage Area Network (SAN)**. (Rack-aware is not available for disaggregated.)

![Basics tab of the disaggregated Azure Local deployment — select Storage Area Network (SAN)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-151738.png)
*Basics tab — add machines and select the SAN storage option. (Source: Microsoft Learn)*

### 3.2 Networking — SAN-based storage

On the **Networking** tab, storage is **SAN based**, so there is **no SMB/storage (replication) network intent** — that's the key difference from a hyperconverged S2D cluster, which needs a dedicated storage-replication network. Configure **Management** and **Compute** intents only (grouped or separated), and give each cluster network its own VLAN ID. RDMA is disabled for cluster networks. Adapter count and intent layout are a general Azure Local design choice, not storage-specific — follow [Microsoft's networking guidance for disaggregated deployments](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated#specify-network-settings).

![Networking tab of the disaggregated Azure Local deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-163448.png)
*Networking tab — Management and Compute intents (no storage intent for SAN). (Source: Microsoft Learn)*

### 3.3 Advanced — select the SAN LUNs

On the **Advanced** tab, select the two SAN LUNs created in Phase 2: the **infrastructure** volume (≥ 250 GB) and the **cluster performance-history** volume (≥ 20 GB). Only LUNs meeting the size minimums appear in the picker.

![Advanced tab of the disaggregated Azure Local deployment — select the infrastructure and performance-history LUNs](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-165343.png)
*Advanced tab — select the infrastructure (≥250 GB) and cluster performance-history (≥20 GB) LUNs. (Source: Microsoft Learn)*

> **Do not delete** the infrastructure or performance-history volumes created during deployment.

> **If the LUNs don't appear (or the wizard reports "disks not properly configured"):** the volumes must be visible **and online on every node** before the picker will accept them. Refreshing the storage cache is often not enough — you may need to bring the disks online on each node (`Get-Disk | Where-Object BusType -eq 'Fibre Channel'` then `Set-Disk -IsOffline $false`), and in some cases **reboot the node** for it to enumerate the new LUNs. Confirm all nodes see both LUNs before continuing.

### 3.4 Validate and deploy

Run **validation**, then **Create**. Validation is strict and will halt the deployment on issues it finds — a couple of common blockers worth clearing first:

- **Dismount any DVD/ISO images** from the nodes. Validation detects mounted virtual media and stops.
- **Leave cluster-traffic NICs unconfigured.** If you manually set an IP address, route, or VLAN on a NIC while testing connectivity, **remove them** (`Remove-NetRoute`, `Remove-NetIPAddress`, and clear the VLAN ID) before deploying — validation flags NICs that already have this configuration and fails, asking you to undo it.

After deployment completes, confirm the cluster is healthy and Arc-connected:

```powershell
Get-Cluster     | Select-Object Name, ClusterFunctionalLevel
Get-ClusterNode | Select-Object Name, State
```

You can also verify in the **Azure portal** on the Azure Local cluster **Overview** page (healthy/connected status) and under **Resources** (all nodes online and healthy), confirming the Cluster Name Object (CNO) is functioning with Azure.

---

## Phase 4: Azure Local Cluster Storage Configuration (Day-2 Workload Volumes)

To add workload storage after deployment, create more FlashArray volumes and promote them to CSVs. The fabric is already zoned from Phase 2.

> **Note:** These steps are executed while connected to a **single** Azure Local node. Once the storage is promoted to a CSV, the configuration synchronizes automatically to all member nodes.

### 4.1 Create and present the workload volume (FlashArray, from your workstation)

```powershell
New-Pfa2Volume     -Array $Conn -Name "<Volume_Name>" -Provisioned <Size_in_TB>TB
New-Pfa2Connection -Array $Conn -VolumeName "<Volume_Name>" -HostGroupName "<Host_Group_Name>"
```

### 4.2 Rescan and identify the disk (on one node)

```powershell
# Open a session to a node
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)

# Refresh the storage stack to detect the new LUN
Update-HostStorageCache

# Locate the new FlashArray disk (Offline / Uninitialized). Record its <Disk_Number>.
Get-Disk

# List MPIO-managed disks and confirm multiple active paths
mpclaim -s -d
mpclaim -s -d <MPIO_Disk_Number>
```

A healthy FlashArray volume shows multiple Active/Optimized paths, the load-balance policy (e.g., Round Robin), and `Controlling DSM: Microsoft DSM`.

> **If the new LUN doesn't show up:** `Update-HostStorageCache` doesn't always trigger enumeration. If `Get-Disk` doesn't list the volume, retry the rescan, and if it still doesn't appear, **reboot the node** — a reboot reliably forces the node to detect newly presented FlashArray LUNs.

### 4.3 Initialize and format the disk

```powershell
Set-Disk -Number <Disk_Number> -IsOffline $false
Initialize-Disk -Number <Disk_Number> -PartitionStyle GPT
$Partition = New-Partition -DiskNumber <Disk_Number> -UseMaximumSize
Get-Partition -DiskNumber <Disk_Number> -PartitionNumber $Partition.PartitionNumber |
    Format-Volume -FileSystem NTFS -AllocationUnitSize 65536 -NewFileSystemLabel "<Volume_Label>" -Confirm:$false
```

NTFS with a 64 KB (65536 byte) allocation unit is recommended for Azure Local to optimize Hyper-V performance and enable block cloning.

### 4.4 Add the disk to the cluster and promote to a CSV

**Option A — automated (single new disk only):**

```powershell
Get-ClusterAvailableDisk -All | Add-ClusterDisk | Add-ClusterSharedVolume
```

> **Warning:** This is a bulk operation — it captures *every* eligible disk not yet in the cluster. If you have multiple new volumes for different purposes, use Option B.

**Option B — targeted:**

```powershell
$ClusterDisk = Get-Disk -Number <Disk_Number> | Add-ClusterDisk
Add-ClusterSharedVolume -Name $ClusterDisk.Name

# Identify available-storage disks if needed
Get-ClusterResource | Where-Object { $_.ResourceType -eq "Physical Disk" }

# Optional: rename the CSV resource to map clearly to the FlashArray volume
(Get-ClusterSharedVolume -Name $ClusterDisk.Name).Name = "<New_CSV_Name>"
```

### 4.5 Verify the CSV

```powershell
Get-ClusterSharedVolume -Name "<CSV_Name>"
```

Confirm the state is **Online** and the **Shared Volume** property is set. CSVs are mounted under `C:\ClusterStorage\` on every node.

### 4.6 Create an Azure Storage Path

Register the CSV as a Storage Path in the Azure portal so Azure Arc-enabled services and Azure VM management can use FlashArray storage.

```powershell
# Find the local CSV path
Get-ClusterSharedVolume | Select-Object Name -ExpandProperty SharedVolumeInfo |
    Select-Object Name, FriendlyVolumeName
```

1. Sign in to the [Azure portal](https://portal.azure.com) and search for **Azure Local**. Select your cluster under **All Systems**.
2. In the left navigation under **Resources**, select **Storage Paths**.
3. Click **+ Create storage path**.
4. Fill in the fields:
   - **File system path:** the local CSV directory, e.g. `C:\ClusterStorage\Volume1`
   - **Name:** a friendly name for the storage path
5. Click **Create**. The Storage Path appears in the portal after a few minutes.

---

## Appendix — Reference Command Block

> **IMPORTANT:** Do **not** run this entire set sequentially. Commands run across different platforms:
> - **Everpure PowerShell SDK** — from a management workstation to configure the FlashArray.
> - **Remote PowerShell / Windows** — inside an Azure Local node session to configure MPIO, disks, and CSVs.
>
> Replace all placeholders (e.g., `<FlashArray_Management_VIP>`, `<Volume_Name>`) before execution.

```powershell
# ============== PRE-DEPLOYMENT ==============

# --- On each Azure Local node (remote session) ---
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
Get-WindowsOptionalFeature -Online -FeatureName MultipathIO      # enabled by default on 2604+; enable with -NoRestart only if Disabled
New-MSDSMSupportedHw -VendorId "PURE" -ProductId "FlashArray"
Remove-MSDSMSupportedHW -VendorId 'Vendor 8' -ProductId 'Product 16' -Confirm:$false  # optional: drop the placeholder entry
Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy RR        # RR <=10 paths, LQD >10 paths
Set-MPIOSetting -NewPathRecoveryInterval 20 -CustomPathRecovery Enabled `
    -NewPDORemovePeriod 20 -NewDiskTimeout 60 `
    -NewPathVerificationState Enabled -NewPathVerificationPeriod 30
Get-InitiatorPort                                          # record ALL WWPNs per node
# Reboot the node after registering the hardware ID

# --- On a management workstation (Everpure SDK v2) ---
if (!(Get-Module -ListAvailable -Name PureStoragePowerShellSDK2)) {
    Install-Module -Name PureStoragePowerShellSDK2 -Force -AllowClobber -Scope CurrentUser
}
Import-Module -Name PureStoragePowerShellSDK2
$Conn = Connect-PFA2Array -Endpoint "<FlashArray_Management_VIP>" -Credential (Get-Credential) -IgnoreCertificateError

New-Pfa2Host         -Array $Conn -Name "<Node_Name>" -Wwns "<WWPN_1>", "<WWPN_2>"   # per node, all WWPNs
New-Pfa2HostGroup    -Array $Conn -Name "<Host_Group_Name>"
New-Pfa2HostGroupHost -Array $Conn -GroupName "<Host_Group_Name>" -MemberName "<Node_1_Name>", "<Node_2_Name>"

# Deployment LUNs (must exist before the wizard)
New-Pfa2Volume     -Array $Conn -Name "<Cluster>-infra"       -Provisioned 250GB
New-Pfa2Volume     -Array $Conn -Name "<Cluster>-perfhistory" -Provisioned 20GB
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-infra"       -HostGroupName "<Host_Group_Name>"
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-perfhistory" -HostGroupName "<Host_Group_Name>"

# ====> Run the disaggregated deployment wizard (Storage = SAN; select the two LUNs) <====

# ============== DAY-2 WORKLOAD VOLUME ==============

# --- On the management workstation ---
New-Pfa2Volume     -Array $Conn -Name "<Volume_Name>" -Provisioned <Size_in_TB>TB
New-Pfa2Connection -Array $Conn -VolumeName "<Volume_Name>" -HostGroupName "<Host_Group_Name>"

# --- On one Azure Local node ---
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
Update-HostStorageCache
Get-Disk
$DiskNumber = <Disk_Number>
Set-Disk -Number $DiskNumber -IsOffline $false
Initialize-Disk -Number $DiskNumber -PartitionStyle GPT
$Partition = New-Partition -DiskNumber $DiskNumber -UseMaximumSize
Get-Partition -DiskNumber $DiskNumber -PartitionNumber $Partition.PartitionNumber |
    Format-Volume -FileSystem NTFS -AllocationUnitSize 65536 -NewFileSystemLabel "<Volume_Label>" -Confirm:$false
$ClusterDisk = Get-Disk -Number $DiskNumber | Add-ClusterDisk
Add-ClusterSharedVolume -Name $ClusterDisk.Name
(Get-ClusterSharedVolume -Name $ClusterDisk.Name).Name = "<New_CSV_Name>"
```

## Related Articles

- [Azure Local Quick Start Guide - Disaggregated iSCSI](../iscsi/QUICKSTART.md)
- [Azure Local Quick Start Guide - Hyperconverged FC](../../hyperconverged/fc/QUICKSTART.md)
- [Azure Local Quick Start Guide - Hyperconverged iSCSI](../../hyperconverged/iscsi/QUICKSTART.md)
- [Azure Local with Everpure Data (Everpure Microsoft Platform Guide)](https://support.everpuredata.com/bundle/m_microsoft_platform_guide/page/Solutions/Microsoft_Platform_Guide/topics/concept/c_azure_local.html)
- [Deploy Azure Local for disaggregated deployments (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated)
- [Supported SAN solutions on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)
- [Setting the MPIO Policy (Everpure)](https://support.everpuredata.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy)
