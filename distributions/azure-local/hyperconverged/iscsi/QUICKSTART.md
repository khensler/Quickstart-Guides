# Azure Local Quick Start Guide - Hyperconverged iSCSI

## Overview

This quick start guide walks through adding an Everpure Data FlashArray to an Azure Local cluster in a **hyperconverged (hybrid)** topology using **iSCSI**. In a hyperconverged deployment the cluster is deployed on local **Storage Spaces Direct (S2D)**, and the FlashArray is attached afterward as **additional** external block storage over iSCSI (TCP/IP). Upon completion, Azure Local VMs and workloads can consume persistent block storage from both S2D and the FlashArray.

> Looking for a **SAN-only** cluster (no local S2D)? See the [Disaggregated iSCSI guide](../../disaggregated/iscsi/QUICKSTART.md). Prefer **Fibre Channel**? See the [Hyperconverged FC guide](../fc/QUICKSTART.md).

> **Microsoft reference:** [Enable External Storage on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage) · [Supported SAN solutions on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)

## Prerequisites

Before beginning, ensure you have:

- **Azure Local cluster deployed on a version that supports external iSCSI SAN storage.** iSCSI external-storage support landed later than FC; confirm your build against [Supported SAN solutions on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements) and [Azure Local release information](https://learn.microsoft.com/en-us/azure/azure-local/release-information) before starting. (The companion disaggregated iSCSI guide targets **2607+**.)
- The cluster is **already deployed on Storage Spaces Direct**, registered with Azure Arc, and healthy in the Azure portal.
- **Dedicated iSCSI NICs (Windows Server 2025 certified NIC and driver)** installed on **all** cluster nodes and cabled to the storage network. Use **dedicated physical ports** — virtual NICs (vNICs) are **not** supported for iSCSI storage.
- Everpure Data FlashArray with **iSCSI enabled**, target portals assigned IP addresses, and IP connectivity established between the FlashArray iSCSI ports and all cluster nodes.
- FlashArray administrator credentials.
- Identical NIC and iSCSI configuration across all cluster nodes.
- PowerShell (run as Administrator) access to every Azure Local node, plus access to the Azure portal.

> **Important:** Because the cluster is deployed on S2D first, **do not present or log in to the FlashArray iSCSI targets until *after* the Azure Local deployment is complete and the cluster is healthy.** Attaching the array earlier can cause the deployment to misidentify iSCSI LUNs as local boot/storage disks. (This is the opposite of the disaggregated/SAN-only model, where infrastructure LUNs must be presented *before* deployment.)

### Supported-configuration constraints

- External SAN supports **block storage** only (here, over iSCSI).
- LUNs must be presented to **all** cluster nodes (no partial presentation) with **consistent LUN IDs**.
- Only **NTFS**-formatted volumes are supported for SAN-backed CSVs (ReFS is not supported for SAN-backed volumes).
- Each SAN LUN must be dedicated to a single CSV (no sharing across clusters).
- MPIO must be configured **consistently across all nodes** before using the volumes.
- The array must support **SCSI-3 Persistent Reservations (PR)** for failover clustering.

## Background

In a hyperconverged configuration, Azure Local uses its in-box **Storage Spaces Direct** pool (built from local drives) as the primary storage, and the Everpure Data FlashArray is added side-by-side as external iSCSI SAN storage. This lets you keep existing S2D investments while placing performance-sensitive or large-capacity workloads on the FlashArray.

The FlashArray uses the **native Microsoft Device Specific Module (MSDSM)** for multipathing — there is **no separate Pure/Everpure DSM to install**. You register the FlashArray vendor/product ID with MSDSM and enable automatic claiming for the iSCSI bus. With iSCSI, redundant paths are delivered over **dedicated iSCSI NICs** rather than Fibre Channel HBAs, and each node must **discover and log in** to the array's iSCSI targets.

## Step-by-Step Instructions

The FlashArray is attached as a **day-2** operation after the S2D cluster is already deployed and healthy.

> Unless a step says otherwise, run the PowerShell on **every** Azure Local node, in an **elevated** PowerShell session.

### Step 1: Confirm the cluster is deployed and healthy

This guide assumes the cluster is already deployed on Storage Spaces Direct (Azure portal deployment with **Storage options → Storage Spaces Direct**). Confirm health before attaching the array:

```powershell
Get-Cluster        | Select-Object Name, ClusterFunctionalLevel
Get-ClusterNode    | Select-Object Name, State
Get-StoragePool    | Select-Object FriendlyName, HealthStatus, OperationalStatus
```

> [Deploy an Azure Local instance using the Azure portal](https://learn.microsoft.com/en-us/azure/azure-local/deploy/deploy-via-portal)

### Step 2: Enable Windows features and the iSCSI initiator; collect IQNs

Azure Local 2604+ enables Multipath I/O (MPIO) by default. Verify it on each node; if it was off (possible on older builds), enabling it requires a reboot.

```powershell
# Verify / enable MPIO
Enable-WindowsOptionalFeature -Online -FeatureName MultipathIO

Get-WindowsOptionalFeature -Online -FeatureName MultipathIO |
    Select-Object FeatureName, State, RestartNeeded
```

If `RestartNeeded` is `True`, perform a rolling reboot of the nodes before continuing.

Enable the Microsoft iSCSI Initiator service (`MSiSCSI`) and set it to start automatically on every node:

```powershell
Set-Service -Name MSiSCSI -StartupType Automatic
Start-Service -Name MSiSCSI
Get-Service -Name MSiSCSI | Select-Object Name, Status, StartType
```

Collect each node's **iSCSI Qualified Name (IQN)** — you (or your storage admin) need these to register hosts on the FlashArray:

```powershell
(Get-InitiatorPort | Where-Object ConnectionType -eq 'iSCSI').NodeAddress
```

> [`Get-InitiatorPort`](https://learn.microsoft.com/en-us/powershell/module/storage/get-initiatorport) · [Install and configure MPIO](https://learn.microsoft.com/en-us/windows-server/storage/mpio/install-and-configure-mpio)

### Step 3: Register the FlashArray with MPIO and configure settings

Run on **each** node. MPIO policy changes take effect only after a reboot (Step 7).

```powershell
# Register the Everpure Data FlashArray with MSDSM so MPIO claims its LUNs
New-MSDSMSupportedHW -VendorId "PURE" -ProductId "FlashArray"

# Remove the generic wildcard entry so MSDSM does not claim non-Pure devices
Remove-MSDSMSupportedHW -VendorId 'Vendor*' -ProductId 'Product*'

# Enable MPIO to automatically claim all iSCSI devices
Enable-MSDSMAutomaticClaim -BusType iSCSI

# Set the global load-balance policy to Round Robin (recommended for FlashArray)
Set-MSDSMGlobalDefaultLoadBalancePolicy -Policy RR

# FlashArray-recommended MPIO timer settings (Everpure lab-tested starting values)
Set-MPIOSetting -NewPathRecoveryInterval 20 -NewPathVerificationPeriod 30 -NewPDORemovePeriod 30
```

> **Microsoft-documented Everpure values:** The official [Enable External Storage](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage) doc lists these Everpure FlashArray-specific overrides. They are compatible with the values above and add path-recovery and disk-timeout settings:
> ```powershell
> Set-MPIOSetting -NewPathRecoveryInterval 20 -CustomPathRecovery Enabled `
>     -NewPDORemovePeriod 20 -NewDiskTimeout 60 -NewPathVerificationState Enabled
> ```

> **Note:** Use `New-MSDSMSupportedHW` (rather than the MPIO GUI) — it enforces the required 8-char Vendor / 16-char Product string formatting automatically.
> For hosts with **more than 10 paths** to a volume, Everpure Data recommends Least Queue Depth (`-Policy LQD`) instead of Round Robin.

> [Everpure Data — Setting the MPIO Policy](https://support.purestorage.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy) · [Azure Local with Everpure](https://support.purestorage.com/bundle/m_microsoft_platform_guide/page/Solutions/Microsoft_Platform_Guide/topics/concept/c_azure_local.html)

### Step 4: Configure the iSCSI network

Run on **each** node. Keep iSCSI NICs **outside Network ATC** (they must not be part of a Management or Compute intent) and configure them manually. Assign each iSCSI NIC a static IP on its storage subnet with **no default gateway**. Use at least two NICs on separate subnets for redundancy.

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

### Step 5: Create hosts and present LUNs on the FlashArray

Now that the S2D deployment is complete and the node iSCSI networking is in place, provision the storage on the FlashArray. Performed on the array (Everpure PowerShell SDK v2 or the GUI):

- Create a **Host** object for each Azure Local node using the IQNs from Step 2 (use `-Iqns`, not `-Wwn`).
- Group all Azure Local hosts into a **Host Group** (e.g., `azurelocal-hg`).
- Create the volume(s) sized for your workload and **connect them to the Host Group** (so every node sees them with consistent LUN IDs).

```powershell
# From a management workstation (not from an Azure Local node — the nodes are security-locked)
Install-Module -Name PureStoragePowerShellSDK2 -Force -AllowClobber
Import-Module -Name PureStoragePowerShellSDK2
$Conn = Connect-PFA2Array -Endpoint "<FlashArray_Management_VIP>" -Credential (Get-Credential) -IgnoreCertificateError

# Create a host per node (by IQN), a host group, and add the hosts
New-Pfa2Host          -Array $Conn -Name "<Node_Name>" -Iqns "<Node_IQN>"   # run once per node
New-Pfa2HostGroup     -Array $Conn -Name "<Host_Group_Name>"
New-Pfa2HostGroupHost -Array $Conn -GroupName "<Host_Group_Name>" -MemberName "<Node_1_Name>", "<Node_2_Name>"

# Create the workload volume and connect it to the host group
New-Pfa2Volume     -Array $Conn -Name "<Volume_Name>" -Provisioned <Size_in_TB>TB
New-Pfa2Connection -Array $Conn -VolumeName "<Volume_Name>" -HostGroupName "<Host_Group_Name>"
```

Confirm with your storage administrator before continuing:

| Item | Required |
| --- | --- |
| Volumes created and connected to the **Host Group** (all nodes) | ✓ |
| Host entries created using the IQNs from Step 2 | ✓ |
| FlashArray iSCSI target portals reachable from every node's iSCSI subnets | ✓ |
| Consistent LUN IDs presented to all nodes | ✓ |

> [FlashArray Admin Guide](https://support.everpuredata.com/r/flasharray-admin-and-cli-reference-guides/flasharray-admin-and-cli-reference-guides)

### Step 6: Log in to the iSCSI targets

Run on **each** node. Unlike Fibre Channel (where LUNs appear automatically once zoning and masking are in place), iSCSI requires each node to **discover the target portals and log in** to the FlashArray targets.

A FlashArray presents a **single iSCSI target IQN for the whole array** (all iSCSI ports share it), so you don't need to hard-code it. `New-IscsiTargetPortal` performs SendTargets discovery against each portal; `Get-IscsiTarget` then returns the array's target IQN, which you pass to `Connect-IscsiTarget`. For real multipathing, establish one session per **(initiator NIC, target portal)** pair — a single bare `Connect-IscsiTarget` creates only one default path.

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

> **`-IsPersistent $true`** ensures the sessions re-establish automatically after a reboot. Confirm this survives a restart (Step 7) since it is essential for CSV availability.

### Step 7: Verify MPIO and reboot

On each node, confirm the registration, then perform a **rolling reboot** to apply the MPIO changes:

```powershell
mpclaim -s -d
Get-MSDSMSupportedHw
Get-MSDSMAutomaticClaimSettings   # confirm iSCSI automatic claim is enabled
```

After the rolling reboot, confirm the iSCSI sessions and paths return on their own:

```powershell
Get-IscsiSession                                        # sessions present again after reboot
Get-IscsiTarget | Where-Object IsConnected -eq $true    # target shows IsConnected = True
mpclaim -s -d                                           # all expected paths restored
```

### Step 8: Verify SAN disks on every node

Run on **every** node and confirm all nodes see the **same** LUNs. Disk numbers may differ between nodes — use `UniqueId` as the authoritative identifier. The FlashArray iSCSI LUNs are separate from the local S2D disks (`BusType` filters them out).

```powershell
# Rescan storage
Update-HostStorageCache

# List iSCSI LUNs only (S2D disks have a different BusType)
Get-Disk | Where-Object BusType -eq 'iSCSI' |
    Select-Object Number, FriendlyName, Size, OperationalStatus, PartitionStyle, BusType |
    Format-Table -AutoSize

# Verify MPIO path count per disk
mpclaim -s -d

# Confirm UniqueId matches across all nodes
Get-Disk | Where-Object BusType -eq 'iSCSI' |
    Select-Object Number, SerialNumber, UniqueId | Format-Table -AutoSize
```

### Step 9: Initialize and format the disk (single node only)

Run on **one** node only. Initialize as GPT and format NTFS with a 64K allocation unit (recommended for CSV). SAN LUNs are Offline by default (`OfflineShared` policy), so bring them online first.

```powershell
$sanDisks = Get-Disk | Where-Object {
    $_.BusType -eq 'iSCSI' -and $_.PartitionStyle -eq 'RAW'
}
foreach ($disk in $sanDisks) {
    Set-Disk -Number $disk.Number -IsOffline $false
    Set-Disk -Number $disk.Number -IsReadOnly $false
    Initialize-Disk -Number $disk.Number -PartitionStyle GPT
    New-Partition -DiskNumber $disk.Number -UseMaximumSize |
        Format-Volume -FileSystem NTFS -AllocationUnitSize 65536 `
            -NewFileSystemLabel "SAN-LUN-$($disk.Number)" -Confirm:$false
}
```

> [`Initialize-Disk`](https://learn.microsoft.com/en-us/powershell/module/storage/initialize-disk) · [`Format-Volume`](https://learn.microsoft.com/en-us/powershell/module/storage/format-volume)

### Step 10: Add the disk to the cluster and create a CSV

After all iSCSI disks are visible and validated, add them to the failover cluster and convert them to Cluster Shared Volumes (CSVs).

```powershell
# Add the SAN disks to the cluster
Get-ClusterAvailableDisk | Add-ClusterDisk

# Convert the available-storage physical disks to CSVs
Get-ClusterResource |
    Where-Object { $_.ResourceType -eq 'Physical Disk' -and $_.OwnerGroup -eq 'Available Storage' } |
    Add-ClusterSharedVolume

# Verify
Get-ClusterSharedVolume | Select-Object Name, State, OwnerNode | Format-Table -AutoSize
Get-ClusterSharedVolume | Select-Object -ExpandProperty SharedVolumeInfo |
    Select-Object FriendlyVolumeName
```

> [Use Cluster Shared Volumes](https://learn.microsoft.com/en-us/windows-server/failover-clustering/failover-cluster-csvs) · [`Add-ClusterSharedVolume`](https://learn.microsoft.com/en-us/powershell/module/failoverclusters/add-clustersharedvolume)

### Step 11: Validate multi-node access

```powershell
# Run cluster storage validation
Test-Cluster -Include Storage

# Confirm the CSV is online on all nodes
Get-ClusterSharedVolume | Select-Object Name, State, OwnerNode
```

CSVs are exposed under `C:\ClusterStorage\` on every node. Write a test file from one node and confirm it is readable from another to validate simultaneous access.

> [`Test-Cluster`](https://learn.microsoft.com/en-us/powershell/module/failoverclusters/test-cluster) / [Validate hardware for a failover cluster](https://learn.microsoft.com/en-us/windows-server/failover-clustering/create-failover-cluster)

### Step 12: Register the CSV storage path in the Azure portal

To place VMs on the SAN volume, register each SAN CSV path in Azure. Only register the **SAN** CSV paths — Azure Local manages the Storage Spaces Direct volumes (such as `Infrastructure` and `UserStorage`) automatically.

1. Sign in to the [Azure portal](https://portal.azure.com) and open your Azure Local cluster resource.
2. Go to **Settings** > **Storage path**.
3. Select **+ Add storage path**.
4. Enter the CSV path, for example `C:\ClusterStorage\Volume1`.
5. Confirm and save. Repeat for each SAN CSV.

### Step 13: Configure for VM workloads (optional)

In Windows Admin Center, the Azure portal, or via Hyper-V, create a new VM and place its VHDX on the registered SAN CSV path (or on an S2D volume, as appropriate for the workload). Start the VM and verify normal operation.

## Troubleshooting

**iSCSI LUNs not visible after rescan**
- Confirm each node has logged in to the targets: `Get-IscsiSession` and `Get-IscsiTarget | Where-Object IsConnected -eq $true`.
- Verify the array maps the volumes to the **Host Group** (all nodes), not to individual hosts only.
- Rescan: `Update-HostStorageCache`
- Confirm IP connectivity from each iSCSI NIC to each FlashArray target portal (`Test-NetConnection <TargetPortalIP> -Port 3260`).
- Verify MPIO registration and iSCSI auto-claim: `Get-MSDSMSupportedHw` and `Get-MSDSMAutomaticClaimSettings`.

**Only one path per disk / no multipathing**
- Establish one session per **(initiator NIC, target portal)** pair — a single bare `Connect-IscsiTarget` creates only one path.
- Confirm both iSCSI NICs have IPs on their storage subnets and can reach the target portals.
- Confirm `-IsMultipathEnabled $true` was used on the connections.

**iSCSI sessions don't return after reboot**
- Confirm the sessions were created with `-IsPersistent $true` (`Get-IscsiTarget` / `Get-IscsiConnection`).
- Confirm the `MSiSCSI` service start type is **Automatic** (Step 2).

**MPIO doesn't claim disks correctly**
- Confirm the registered IDs are exactly `PURE` / `FlashArray`: `Get-MSDSMSupportedHw`
- Confirm `Enable-MSDSMAutomaticClaim -BusType iSCSI` was run. If you enabled it *after* the LUNs were already visible, reboot the node so MSDSM can re-enumerate, then `mpclaim -s -d`.

**Local S2D disks appear alongside SAN LUNs**
- This is expected in a hyperconverged cluster. Filter by `BusType -eq 'iSCSI'` to target only FlashArray LUNs; never initialize or reformat S2D pool disks.

**`Test-Cluster` storage validation fails**
- All nodes must detect the same set of shared disks with consistent LUN IDs.
- Confirm the FlashArray presents the same `UniqueId` to every node.
- Confirm the array supports SCSI-3 Persistent Reservations.

**Can't add disks as CSVs**
- Disks must be online and NTFS-formatted: `Get-Disk | Select Number, OperationalStatus, PartitionStyle` and `Get-Volume`
- The disk must be a cluster resource: `Get-ClusterResource | Where-Object ResourceType -eq 'Physical Disk'`

**Storage path creation fails in the Azure portal**
- The CSV must be online and accessible from all nodes.
- The path must use the form `C:\ClusterStorage\Volume1`.
- The cluster must be registered and healthy in Azure.

**Performance lower than expected**
- Confirm MPIO is claiming all paths (`mpclaim -s -d`) and the load-balance policy is RR (or LQD for >10 paths).
- Confirm jumbo frames (MTU) are set consistently end-to-end across NICs, switches, and FlashArray ports.
- Check the FlashArray dashboard for any QoS/throttling policies.

## Additional Notes

- The Everpure Data FlashArray uses the **native Windows MSDSM** for multipathing — there is no separate DSM to install. Apply the MPIO timer settings (Step 3) consistently on every node.
- Keep iSCSI NICs on **dedicated physical ports**, outside Network ATC, with static IPs and **no default gateway**; vNICs are not supported for iSCSI storage.
- In a hyperconverged cluster, S2D and FlashArray volumes coexist; place each workload on the tier that best fits its capacity and performance needs.
- Each SAN LUN maps to a single CSV; size LUNs according to per-CSV capacity and IOPS needs.
- Snapshot and replication policies can be configured on the FlashArray for Azure Local CSV backup workflows.
- Only NTFS is supported for SAN-backed CSVs; ReFS is not supported for SAN-backed volumes.

## Related Articles

- [Azure Local Quick Start Guide - Disaggregated iSCSI](../../disaggregated/iscsi/QUICKSTART.md)
- [Azure Local Quick Start Guide - Hyperconverged FC](../fc/QUICKSTART.md)
- [Enable External Storage on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage)
- [Supported SAN solutions on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)
- [Everpure Data — Azure Local integration](https://support.purestorage.com/bundle/m_microsoft_platform_guide/page/Solutions/Microsoft_Platform_Guide/topics/concept/c_azure_local.html)
- [Everpure Data FlashArray MPIO Configuration for Windows Server](https://support.purestorage.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy)
