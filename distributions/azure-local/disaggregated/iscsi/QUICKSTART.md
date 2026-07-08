# Azure Local with Everpure FlashArray Quick Start Guide for Disaggregated Deployments (iSCSI)

This guide provides a high-level workflow for integrating the Everpure FlashArray as the **only** block storage for a **disaggregated** Azure Local (formerly Azure Stack HCI) deployment over **iSCSI**. In a disaggregated deployment there is no local Storage Spaces Direct (S2D) — compute runs on the Azure Local nodes while all cluster storage is served from the FlashArray over iSCSI (TCP/IP). This combines the cloud-integrated benefits of Azure Local with the high-performance, data-reduced storage of FlashArray, and lets compute and storage scale independently.

> **This document is based heavliy on the official Microsoft documentation.**  [Deploy Azure Local using the Azure portal for disaggregated deployments](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated) · [Enable External Storage on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage)

> **Looking for Fibre Channel instead?** See the [Disaggregated FC guide](../fc/QUICKSTART.md). **Looking for a hyperconverged (S2D + FlashArray) cluster?** See the [Hyperconverged FC guide](../../hyperconverged/fc/QUICKSTART.md).

## Prerequisites to Using the Quick Start Guide

Before you begin, ensure that the following requirements are met:

### Everpure FlashArray

- A deployed and configured Everpure FlashArray.
- **iSCSI** must be enabled and configured on the array, with iSCSI interfaces (target portals) assigned IP addresses and IP connectivity established between the FlashArray iSCSI ports and **all** Azure Local nodes.
- See the [SAN Guidelines for Maximizing FlashArray Performance](https://support.purestorage.com/bundle/m_microsoft_platform_guide).
- **Minimum Recommended Purity Version: 6.5.3**

### Azure Local Deployment (Base)

Unlike a hyperconverged cluster, a **disaggregated cluster is deployed *onto* the FlashArray** — so the FlashArray host/volume setup and node MPIO/iSCSI configuration happen **before and during** the Azure Local deployment, not after.

- Machines from the [Azure Local Catalog](https://aka.ms/AzureStackHCICatalog) racked, with the OS preinstalled and **registered with Azure Arc** (deployment permissions assigned). The cluster itself is created as part of this guide.
- Each node requires its own **local OS boot media** — only the cluster *data/infrastructure* storage comes from the SAN.
- Network interface card (NIC) firmware and driver versions must match the [Azure Local hardware catalog](https://www.windowsservercatalog.com/) requirements, and **all nodes must use identical NIC configurations**.
- **Minimum Azure Local Version: 2607**
- A disaggregated instance supports **1 to 64 machines**. **Rack-aware** clusters are *not* supported with disaggregated deployments.

> **Important — present the deployment LUNs before you run the wizard.** The disaggregated deployment wizard requires you to select two existing SAN LUNs (an **infrastructure** volume ≥ **250 GB** and a **cluster performance-history** volume ≥ **20 GB**). These LUNs must already be mapped and connected over iSCSI to all nodes when you start the wizard.

## Workflow Overview

At a high level, the disaggregated Azure Local integration with FlashArray over iSCSI includes the following phases:

1. **Configure the Azure Local nodes** — enable and tune MPIO, enable the iSCSI initiator, and configure the iSCSI network (before deployment).
2. **Everpure FlashArray setup** — create hosts (by IQN), a host group, and the infrastructure + performance-history volumes, then connect the nodes to the iSCSI targets (before deployment).
3. **Deploy the disaggregated Azure Local cluster** — run the portal wizard with **Storage = SAN** and select the two LUNs.
4. **Azure Local cluster storage configuration** — add day-2 workload volumes as Cluster Shared Volumes (CSVs).

While graphical interfaces such as Windows Admin Center or Failover Cluster Manager are available for setup and administration, **PowerShell is the recommended method** for the initial setup. It provides precision, consistency across nodes, and scriptability. This guide focuses on PowerShell-based execution, supplemented by GUI screenshots to illustrate key validation points.

> For the best experience, use **PowerShell 7.6 or later** when performing the steps in this guide.

> **Note on naming:** Azure does **not** support underscores (`_`) for these resource types. While the FlashArray is flexible with naming, use **hyphens (`-`)** for your Host, Host Group, and Volume names to remain fully compatible with Azure Arc-enabled services.

---

## Phase 1: Configure the Azure Local Nodes

Multipath I/O (MPIO) is a critical configuration requirement for Azure Local nodes. It provides hardware resiliency by establishing redundant physical paths between the node and the storage array, and facilitates performance load balancing by distributing I/O traffic across all active paths. For iSCSI, those redundant paths are delivered over **dedicated iSCSI NICs** rather than Fibre Channel HBAs.

### 1.1 NIC Driver and Firmware

Before software configuration, the physical NICs used for iSCSI must run vendor-validated driver/firmware versions — default drivers are insufficient for production.

- All iSCSI NICs must run driver and firmware versions found in the [Windows Server Catalog for Azure Local](https://www.windowsservercatalog.com/).
- The NIC must also be supported by the server vendor for the specific server model in use.
- Use **dedicated physical ports** for iSCSI. Virtual NICs (vNICs) are **not** supported for iSCSI storage.
- Install and confirm that the latest validated drivers are running on the NICs.

### 1.2 Enable the MPIO Feature

The MPIO framework must be installed and active on **every** node in the cluster.

> **Attention:** To remotely run PowerShell on an Azure Local node, enable Remote Management on the target node using the **SConfig** utility (Option 4) and ensure the firewall allows WinRM traffic.

> **Note:** All setup commands in this section must be executed individually on **each** Azure Local node.

> **Note:** To run remotely from a workstation first enter a new remote session:

```powershell
# Open a remote session to a node (run from your management workstation)
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
```
> **Note:** Commands from here on should either be run in the remote session or locally on the hypervisor node.

Azure Local **2604 and later enables MPIO by default**, so this step is primarily a verification. If MPIO is not enabled (possible on earlier builds), enabling it requires a reboot.

```powershell
# Enable the MPIO feature (no-op if already enabled)
Enable-WindowsOptionalFeature -Online -FeatureName MultipathIO

# Verify — RestartNeeded indicates whether a reboot is required
Get-WindowsOptionalFeature -Online -FeatureName MultipathIO |
    Select-Object FeatureName, State, RestartNeeded
```

### 1.3 Enable the iSCSI Initiator Service

The Microsoft iSCSI Initiator service (`MSiSCSI`) must be running and set to start automatically on every node.

```powershell
Set-Service -Name MSiSCSI -StartupType Automatic
Start-Service -Name MSiSCSI
Get-Service -Name MSiSCSI | Select-Object Name, Status, StartType
```

### 1.4 Claim FlashArray as an MPIO Target

By default the OS does not claim external arrays for multipathing. Register the FlashArray hardware IDs with the Microsoft Device Specific Module (MSDSM).

```powershell
New-MSDSMSupportedHw -VendorId "PURE" -ProductId "FlashArray"
```

This registers Everpure devices as MPIO-capable. Modern PowerShell automatically handles the character padding for these IDs.

Microsoft recommends removing the generic vendor wildcard entry so MSDSM does **not** automatically claim non-Pure devices:

```powershell
Remove-MSDSMSupportedHW -VendorId 'Vendor*' -ProductId 'Product*'
```

Enable MPIO to automatically claim all iSCSI devices:

```powershell
Enable-MSDSMAutomaticClaim -BusType iSCSI
```

> **Note:** A **reboot is required** after these changes for MSDSM to begin claiming the FlashArray. If you enable auto-claim *after* LUNs are already visible, restart the node so MSDSM can re-enumerate the devices.

### 1.5 Configure MPIO Best Practices

Set the global load-balancing policy according to FlashArray standards:

- **10 or fewer paths:** Round Robin (RR).
- **More than 10 paths:** Least Queue Depth (LQD).

```powershell
Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy RR    # 10 or fewer paths
# Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy LQD  # more than 10 paths
```

> For a deeper dive, see the [Setting the MPIO Policy](https://support.purestorage.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy) KB. Round Robin with Subset (RRWS) is also an option for high path counts but must be set per-volume (it cannot be a global default).

### 1.6 Configure Path Verification and Timeouts

Tuning MPIO timers prevents premature path failovers and lets the system recover gracefully from momentary network hiccups.

```powershell
Set-MPIOSetting -NewPathRecoveryInterval 20 -NewPathVerificationPeriod 30 -NewPDORemovePeriod 30
```

`NewPDORemovePeriod` determines how long the OS waits for a failed path to recover. Holding failover for 30 seconds lets MPIO complete a path-level failover before the Cluster Storage Service sees the disk as "gone" and prematurely triggers a node failover.

> **Note:** These are recommended starting values from Everpure lab testing. Workloads with specific latency requirements or complex fabrics may require additional tuning.

> **Microsoft-documented Everpure values:** The official [Enable External Storage](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage) doc lists these Everpure FlashArray-specific overrides. They are compatible with the values above and add path-recovery and disk-timeout settings:
> ```powershell
> Set-MPIOSetting -NewPathRecoveryInterval 20 -CustomPathRecovery Enabled `
>     -NewPDORemovePeriod 20 -NewDiskTimeout 60 -NewPathVerificationState Enabled
> ```

### 1.7 Configure the iSCSI Network

Keep iSCSI NICs **outside Network ATC** and configure them manually. Assign each iSCSI NIC a static IP on its storage subnet with **no default gateway**. Use at least two NICs on separate subnets for redundancy.

```powershell
# Rename the dedicated iSCSI adapters for clarity
Rename-NetAdapter -Name "Ethernet 3" -NewName "iSCSI-NIC-A"
Rename-NetAdapter -Name "Ethernet 4" -NewName "iSCSI-NIC-B"

# Static IPs on the storage subnets — no default gateway on iSCSI NICs
New-NetIPAddress -InterfaceAlias "iSCSI-NIC-A" -IPAddress 10.30.30.11 -PrefixLength 24
New-NetIPAddress -InterfaceAlias "iSCSI-NIC-B" -IPAddress 10.31.31.11 -PrefixLength 24
```

> **Note:** Do **not** configure a default gateway on iSCSI NICs.

Optionally, configure consistent MTU (jumbo frames) across the entire iSCSI path, and VLAN tags only if the switch ports are trunked:

```powershell
Set-NetAdapterAdvancedProperty -Name "iSCSI-NIC-A" -RegistryKeyword "*JumboPacket" -RegistryValue 9014
Set-NetAdapterAdvancedProperty -Name "iSCSI-NIC-B" -RegistryKeyword "*JumboPacket" -RegistryValue 9014

# Only when switch ports are configured as trunk ports
Set-NetAdapter -Name "iSCSI-NIC-A" -VlanID 500
Set-NetAdapter -Name "iSCSI-NIC-B" -VlanID 600
```

If the FlashArray iSCSI target portals are on a different subnet, add persistent /32 routes for each target portal on both iSCSI NICs:

```powershell
New-NetRoute -DestinationPrefix <TargetPortalIP>/32 -InterfaceAlias "iSCSI-NIC-A" -NextHop <GatewayIP> -PolicyStore PersistentStore
New-NetRoute -DestinationPrefix <TargetPortalIP>/32 -InterfaceAlias "iSCSI-NIC-B" -NextHop <GatewayIP> -PolicyStore PersistentStore
```

Optionally, if iSCSI shares Ethernet infrastructure with other traffic, tag iSCSI with priority 4 and use ETS to reserve bandwidth:

```powershell
New-NetQosPolicy -Name "iSCSI" -IPDstPortStart 3260 -IPDstPortEnd 3260 -IPProtocol TCP -PriorityValue8021Action 4
```

### 1.8 Collect IQNs and Verify Node Readiness

Before moving to FlashArray preparation, verify the staging and collect each node's **iSCSI Qualified Name (IQN)** — you'll register it on the array in Phase 2.

```powershell
# Confirm timers
Get-MPIOSetting

# Confirm global policy returns RR (or LQD)
Get-MSDSMGlobalDefaultLoadBalancePolicy

# Confirm PURE / FlashArray appear in the supported hardware list
Get-MSDSMSupportedHw

# Confirm iSCSI automatic claim is enabled
Get-MSDSMAutomaticClaimSettings

# Record the node IQN — needed in Phase 2
(Get-InitiatorPort | Where-Object ConnectionType -eq 'iSCSI').NodeAddress
```

### 1.9 Repeat for all Azure Local Nodes

Repeat Phase 1 steps for each node.

---

## Phase 2: Everpure FlashArray Setup

With the nodes prepared and their IQNs collected, provision the storage on the FlashArray. This guide uses the **Everpure PowerShell SDK v2** for repeatability.  The GUI may be used for these actions as well.  See the [FlashArray Admin Guide](https://support.everpuredata.com/r/flasharray-admin-and-cli-reference-guides/flasharray-admin-and-cli-reference-guides).

> **Note:** This guide assumes the FlashArray iSCSI interfaces (target portals) already have IP addresses assigned and are reachable from the node iSCSI subnets. Consult your network provider for switch/VLAN configuration.

> **Run these from a management workstation — not from an Azure Local node or a remote PS session to an Azure Local node** (the nodes are security-locked).

```powershell
# Install and import the Everpure PowerShell SDK v2
Install-Module -Name PureStoragePowerShellSDK2 -Force -AllowClobber
Import-Module -Name PureStoragePowerShellSDK2

# Connect to the FlashArray management VIP
$Conn = Connect-PFA2Array -Endpoint "<FlashArray_Management_VIP>" -Credential (Get-Credential) -IgnoreCertificateError
```

### 2.1 Create Host Objects

Create a host object for **every** node, mapping its IQN (from Phase 1.8). Use the `-Iqns` parameter (iSCSI) instead of `-Wwn` (Fibre Channel).

```powershell
# Run once per node
New-Pfa2Host -Array $Conn -Name "<Node_Name>" -Iqns "<Node_IQN>"
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

A disaggregated deployment requires **two** volumes to exist before the wizard runs:

| Volume | Minimum size | Purpose |
| --- | --- | --- |
| Infrastructure volume | **250 GB** | Cluster infrastructure storage |
| Cluster performance-history volume | **20 GB** | Performance history |

```powershell
# Infrastructure volume (>= 250 GB)
New-Pfa2Volume -Array $Conn -Name "<Cluster>-infra" -Provisioned 250GB

# Cluster performance-history volume (>= 20 GB)
New-Pfa2Volume -Array $Conn -Name "<Cluster>-perfhistory" -Provisioned 20GB
```

> Size the infrastructure volume according to your cluster's needs; 250 GB is the minimum the wizard accepts. Workload volumes are created later in Phase 4.

### 2.4 Connect the Volumes to the Host Group

Mapping to the Host Group (not individual hosts) makes the storage visible to all nodes with **consistent LUN IDs**.

```powershell
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-infra"       -HostGroupName "<Host_Group_Name>"
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-perfhistory" -HostGroupName "<Host_Group_Name>"
```

The FlashArray is now presenting the infrastructure and performance-history LUNs to all node hosts.

### 2.5 Connect the Nodes to the iSCSI Targets

Unlike Fibre Channel (where LUNs appear automatically once zoning and masking are in place), iSCSI requires each node to **discover the target portals and log in** to the FlashArray targets. Run these commands **on each Azure Local node** (in a remote session), using the FlashArray iSCSI target portal IP(s) from both node iSCSI NICs.

A FlashArray presents a **single iSCSI target IQN for the whole array** (all iSCSI ports share it), so you don't need to hard-code it. `New-IscsiTargetPortal` performs SendTargets discovery against each portal; `Get-IscsiTarget` then returns the array's target IQN, which you pass to `Connect-IscsiTarget`.

> **`Connect-IscsiTarget` always requires a target identity.** `-NodeAddress` (the target IQN) is a **mandatory** parameter; `-TargetPortalAddress` / `-InitiatorPortalAddress` only *scope the path* a session uses and cannot identify the target on their own. You can't "connect by portal IP only" — but you can supply the IQN dynamically (`(Get-IscsiTarget).NodeAddress`) instead of typing it. You do **not** attach LUNs individually: iSCSI login is per-target, and every volume the array masks to this node's initiator IQN appears automatically after a rescan.

For real multipathing, establish one session per **(initiator NIC, target portal)** pair — a single bare `Connect-IscsiTarget` creates only one default path.

```powershell
# Discover the FlashArray target portals (SendTargets) — one line per initiator NIC / target portal
New-IscsiTargetPortal -TargetPortalAddress <FA_TargetPortalIP_1> -InitiatorPortalAddress 10.30.30.11
New-IscsiTargetPortal -TargetPortalAddress <FA_TargetPortalIP_2> -InitiatorPortalAddress 10.31.31.11

# Grab the array's target IQN dynamically (a FlashArray has exactly one)
$target = Get-IscsiTarget

# Establish an MPIO session per initiator-NIC / target-portal pair
Connect-IscsiTarget -NodeAddress $target.NodeAddress `
    -InitiatorPortalAddress 10.30.30.11 -TargetPortalAddress <FA_TargetPortalIP_1> `
    -IsPersistent $true -IsMultipathEnabled $true
Connect-IscsiTarget -NodeAddress $target.NodeAddress `
    -InitiatorPortalAddress 10.31.31.11 -TargetPortalAddress <FA_TargetPortalIP_2> `
    -IsPersistent $true -IsMultipathEnabled $true
```

> **More than one array?** `Get-IscsiTarget` aggregates **every** target this node has discovered, so `$target` would hold multiple IQNs. Filter to the FlashArray before connecting, e.g. `$target = Get-IscsiTarget | Where-Object NodeAddress -like '*purestorage*'`, or pass the specific `-NodeAddress` explicitly.

Verify the LUNs are visible with multiple active paths before deploying:

```powershell
Update-HostStorageCache
Get-Disk | Where-Object BusType -eq 'iSCSI' | Select-Object Number, FriendlyName, OperationalStatus, Size
mpclaim -s -d
```

The infrastructure and performance-history LUNs should now be visible to all nodes, ready for the deployment wizard.

> **Confirm persistence survives a reboot.** Because `-IsPersistent $true` was used, the iSCSI sessions should re-establish automatically after a restart — this is essential, since all cluster storage arrives over iSCSI. Reboot the node, then verify the sessions and paths return on their own:
> ```powershell
> Get-IscsiSession                        # sessions present again after reboot
> Get-IscsiTarget | Where-Object IsConnected -eq $true   # target shows IsConnected = True
> Get-Disk | Where-Object BusType -eq 'iSCSI'            # LUNs reattached
> mpclaim -s -d                           # all expected paths restored
> ```
> If a session does not return, confirm the target is registered as persistent with `Get-IscsiTarget` / `Get-IscsiConnection` and that the `MSiSCSI` service start type is **Automatic** (Phase 1.3).

---

## Phase 3: Deploy the Disaggregated Azure Local Cluster

Run the deployment from the Azure portal. The selections below differ from a standard S2D (hyperconverged) deployment. The wizard flow is identical for FC and iSCSI — the storage option is simply **SAN**; the transport (iSCSI) is established on the nodes in Phases 1–2.

> Full reference: [Deploy Azure Local using the Azure portal for disaggregated deployments](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated).

### 3.1 Basics — choose SAN storage

On the **Basics** tab, set **Storage options** to **Storage Area Network (SAN)**. (Rack-aware is not available for disaggregated.)

![Basics tab of the disaggregated Azure Local deployment — select Storage Area Network (SAN)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-151738.png)
*Basics tab — add machines and select the SAN storage option. (Source: Microsoft Learn)*

### 3.2 Networking — SAN-based storage

On the **Networking** tab, storage is **SAN based**, so there is no SMB/storage network intent. Configure **Management** and **Compute** intents only (grouped or separated). RDMA is disabled for cluster networks.

> **iSCSI note:** The dedicated iSCSI NICs you configured in Phase 1.7 are **not** managed by Network ATC and must **not** be added to a Management or Compute intent. Keep them isolated on their own adapters.

![Networking tab of the disaggregated Azure Local deployment](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-163448.png)
*Networking tab — Management and Compute intents (no storage intent for SAN). (Source: Microsoft Learn)*

### 3.3 Advanced — select the SAN LUNs

On the **Advanced** tab, select the two SAN LUNs created in Phase 2: the **infrastructure** volume (≥ 250 GB) and the **cluster performance-history** volume (≥ 20 GB). Only LUNs meeting the size minimums appear in the picker.

![Advanced tab of the disaggregated Azure Local deployment — select the infrastructure and performance-history LUNs](https://learn.microsoft.com/en-us/azure/azure-local/deploy/media/deploy-via-portal-disaggregated/screenshot-2026-04-14-165343.png)
*Advanced tab — select the infrastructure (≥250 GB) and cluster performance-history (≥20 GB) LUNs. (Source: Microsoft Learn)*

> **Do not delete** the infrastructure or performance-history volumes created during deployment.

### 3.4 Validate and deploy

Run **validation**, then **Create**. After deployment completes, confirm the cluster is healthy and Arc-connected:

```powershell
Get-Cluster     | Select-Object Name, ClusterFunctionalLevel
Get-ClusterNode | Select-Object Name, State
```

You can also verify in the **Azure portal** on the Azure Local cluster **Overview** page (healthy/connected status) and under **Resources** (all nodes online and healthy), confirming the Cluster Name Object (CNO) is functioning with Azure.

---

## Phase 4: Azure Local Cluster Storage Configuration (Day-2 Workload Volumes)

To add workload storage after deployment, create more FlashArray volumes and promote them to CSVs. The iSCSI sessions established in Phase 2.5 are persistent, so new volumes mapped to the existing host group appear on the nodes after a storage rescan — no new target login is required.

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
Get-Disk | Where-Object BusType -eq 'iSCSI'

# List MPIO-managed disks and confirm multiple active paths
mpclaim -s -d
mpclaim -s -d <MPIO_Disk_Number>
```

A healthy FlashArray volume shows multiple Active/Optimized paths, the load-balance policy (e.g., Round Robin), and `Controlling DSM: Microsoft DSM`.

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
> - **Remote PowerShell / Windows** — inside an Azure Local node session to configure MPIO, iSCSI, disks, and CSVs.
>
> Replace all placeholders (e.g., `<FlashArray_Management_VIP>`, `<Volume_Name>`, `<FA_TargetPortalIP>`) before execution.

```powershell
# ============== PRE-DEPLOYMENT ==============

# --- On each Azure Local node (remote session) ---
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
Enable-WindowsOptionalFeature -Online -FeatureName MultipathIO   # enabled by default on 2604+
Set-Service -Name MSiSCSI -StartupType Automatic; Start-Service -Name MSiSCSI
New-MSDSMSupportedHw -VendorId "PURE" -ProductId "FlashArray"
Remove-MSDSMSupportedHW -VendorId 'Vendor*' -ProductId 'Product*'  # don't claim non-Pure devices
Enable-MSDSMAutomaticClaim -BusType iSCSI
Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy RR        # RR <=10 paths, LQD >10 paths
Set-MPIOSetting -NewPathRecoveryInterval 20 -NewPathVerificationPeriod 30 -NewPDORemovePeriod 30
# Configure dedicated iSCSI NICs (static IPs, no gateway)
New-NetIPAddress -InterfaceAlias "iSCSI-NIC-A" -IPAddress 10.30.30.11 -PrefixLength 24
New-NetIPAddress -InterfaceAlias "iSCSI-NIC-B" -IPAddress 10.31.31.11 -PrefixLength 24
(Get-InitiatorPort | Where-Object ConnectionType -eq 'iSCSI').NodeAddress   # record node IQN
# Reboot the node after registering the hardware ID / enabling auto-claim

# --- On a management workstation (Everpure SDK v2) ---
if (!(Get-Module -ListAvailable -Name PureStoragePowerShellSDK2)) {
    Install-Module -Name PureStoragePowerShellSDK2 -Force -AllowClobber -Scope CurrentUser
}
Import-Module -Name PureStoragePowerShellSDK2
$Conn = Connect-PFA2Array -Endpoint "<FlashArray_Management_VIP>" -Credential (Get-Credential) -IgnoreCertificateError

New-Pfa2Host         -Array $Conn -Name "<Node_Name>" -Iqns "<Node_IQN>"   # per node
New-Pfa2HostGroup    -Array $Conn -Name "<Host_Group_Name>"
New-Pfa2HostGroupHost -Array $Conn -GroupName "<Host_Group_Name>" -MemberName "<Node_1_Name>", "<Node_2_Name>"

# Deployment LUNs (must exist before the wizard)
New-Pfa2Volume     -Array $Conn -Name "<Cluster>-infra"       -Provisioned 250GB
New-Pfa2Volume     -Array $Conn -Name "<Cluster>-perfhistory" -Provisioned 20GB
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-infra"       -HostGroupName "<Host_Group_Name>"
New-Pfa2Connection -Array $Conn -VolumeName "<Cluster>-perfhistory" -HostGroupName "<Host_Group_Name>"

# --- On each Azure Local node (remote session): log in to the iSCSI targets ---
New-IscsiTargetPortal -TargetPortalAddress <FA_TargetPortalIP_1> -InitiatorPortalAddress 10.30.30.11
New-IscsiTargetPortal -TargetPortalAddress <FA_TargetPortalIP_2> -InitiatorPortalAddress 10.31.31.11
$target = Get-IscsiTarget    # FlashArray = single target IQN; filter if multiple arrays discovered
Connect-IscsiTarget -NodeAddress $target.NodeAddress -InitiatorPortalAddress 10.30.30.11 -TargetPortalAddress <FA_TargetPortalIP_1> -IsPersistent $true -IsMultipathEnabled $true
Connect-IscsiTarget -NodeAddress $target.NodeAddress -InitiatorPortalAddress 10.31.31.11 -TargetPortalAddress <FA_TargetPortalIP_2> -IsPersistent $true -IsMultipathEnabled $true
Update-HostStorageCache
mpclaim -s -d

# ====> Run the disaggregated deployment wizard (Storage = SAN; select the two LUNs) <====

# ============== DAY-2 WORKLOAD VOLUME ==============

# --- On the management workstation ---
New-Pfa2Volume     -Array $Conn -Name "<Volume_Name>" -Provisioned <Size_in_TB>TB
New-Pfa2Connection -Array $Conn -VolumeName "<Volume_Name>" -HostGroupName "<Host_Group_Name>"

# --- On one Azure Local node (existing iSCSI sessions pick up the new LUN) ---
Enter-PSSession -ComputerName <Node_Name> -Credential (Get-Credential)
Update-HostStorageCache
Get-Disk | Where-Object BusType -eq 'iSCSI'
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

- [Azure Local Quick Start Guide - Disaggregated FC](../fc/QUICKSTART.md)
- [Azure Local Quick Start Guide - Hyperconverged FC](../../hyperconverged/fc/QUICKSTART.md)
- [Azure Local with Everpure (Everpure Microsoft Platform Guide)](https://support.purestorage.com/bundle/m_microsoft_platform_guide/page/Solutions/Microsoft_Platform_Guide/topics/concept/c_azure_local.html)
- [Enable External Storage on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage)
- [Deploy Azure Local for disaggregated deployments (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal-disaggregated)
- [Supported SAN solutions on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)
- [Setting the MPIO Policy (Everpure)](https://support.purestorage.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy)
