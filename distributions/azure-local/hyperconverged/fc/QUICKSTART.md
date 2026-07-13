# Azure Local Quick Start Guide - Hybrid FC

## Overview

This quick start guide walks through adding an Everpure Data FlashArray to an Azure Local cluster in a **hybrid** topology using Fibre Channel (FC). In a hybrid deployment the cluster is deployed on local **Storage Spaces Direct (S2D)**, and the FlashArray is attached afterward as **additional** external block storage. Upon completion, Azure Local VMs and workloads can consume persistent block storage from both S2D and the FlashArray over FC.

> Looking for a **SAN-only** cluster (no local S2D)? See the [Disaggregated FC guide](../../disaggregated/fc/QUICKSTART.md).

> **Microsoft reference:** [Enable External Storage on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage) · [Supported SAN solutions on Azure Local](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)

## Prerequisites

Before beginning, ensure you have:

- **Azure Local cluster deployed with version 2604 or later** (FC SAN integration is generally available starting in 2604). See [Azure Local release information](https://learn.microsoft.com/en-us/azure/azure-local/release-information).
- The cluster is **already deployed on Storage Spaces Direct**, registered with Azure Arc, and healthy in the Azure portal.
- **Fibre Channel HBAs (Windows Server 2025 certified HBA and driver)** installed on **all** cluster nodes and cabled to the FC fabric.
- Everpure Data FlashArray accessible on the FC fabric with management access configured and available capacity.
- FlashArray administrator credentials.
- Identical HBA configuration and FC zoning across all cluster nodes.
- PowerShell (run as Administrator) access to every Azure Local node, plus access to the Azure portal.

> **Important:** Because the cluster is deployed on S2D first, **do not zone in the FC HBA WWNs until *after* the Azure Local deployment is complete.** Zoning the array in earlier can cause the deployment to misidentify FC LUNs as local boot/storage disks. (This is the opposite of the disaggregated/SAN-only model, where infrastructure LUNs must be presented *before* deployment.)

### Supported-configuration constraints

- External SAN supports **block storage over Fibre Channel only**.
- LUNs must be presented to **all** cluster nodes (no partial presentation) with **consistent LUN IDs**.
- Only **NTFS**-formatted volumes are supported for SAN-backed CSVs (ReFS is not supported for SAN-backed volumes).
- Each SAN LUN must be dedicated to a single CSV (no sharing across clusters).
- MPIO must be configured **consistently across all nodes** before using the volumes.
- The array must support **SCSI-3 Persistent Reservations (PR)** for failover clustering.

## Background

In a hybrid configuration, Azure Local uses its in-box **Storage Spaces Direct** pool (built from local drives) as the primary storage, and the Everpure Data FlashArray is added side-by-side as external FC SAN storage. This lets you keep existing S2D investments while placing performance-sensitive or large-capacity workloads on the FlashArray.

The FlashArray uses the **native Microsoft Device Specific Module (MSDSM)** for multipathing — there is **no separate Pure/Everpure DSM to install**. You simply register the FlashArray vendor/product ID with MSDSM.

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

### Step 2: Enable Windows features and collect initiator IDs

Azure Local 2604+ enables Multipath I/O (MPIO) by default. Verify it on each node; if it was off (possible on older builds), enabling it requires a reboot.

```powershell
# Verify / enable MPIO
Enable-WindowsOptionalFeature -Online -FeatureName MultipathIO

Get-WindowsOptionalFeature -Online -FeatureName MultipathIO |
    Select-Object FeatureName, State, RestartNeeded
```

If `RestartNeeded` is `True`, perform a rolling reboot of the nodes before continuing.

Collect each node's FC **World Wide Port Names (WWPNs)** — you (or your storage admin) need these to register hosts and configure zoning on the FlashArray:

```powershell
Get-InitiatorPort | Where-Object ConnectionType -eq 'Fibre Channel' |
    Select-Object NodeAddress, PortAddress, ConnectionType | Format-Table -AutoSize
```

> [`Get-InitiatorPort`](https://learn.microsoft.com/en-us/powershell/module/storage/get-initiatorport) · [Install and configure MPIO](https://learn.microsoft.com/en-us/windows-server/storage/mpio/install-and-configure-mpio)

### Step 3: Register the FlashArray with MPIO and configure settings

Run on **each** node. MPIO policy changes take effect only after a reboot (Step 5).

```powershell
# Register the Everpure Data FlashArray with MSDSM so MPIO claims its LUNs
New-MSDSMSupportedHW -VendorId "PURE" -ProductId "FlashArray"

# Remove the generic wildcard entry so MSDSM does not claim non-Pure devices
Remove-MSDSMSupportedHW -VendorId 'Vendor*' -ProductId 'Product*'

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

### Step 4: Create hosts, zone the fabric, and present LUNs on the FlashArray

Now that the S2D deployment is complete, it is safe to zone the FC fabric. Performed on the FlashArray and FC switches:

- Create a **Host** object for each Azure Local node using the WWPNs from Step 2.
- Group all Azure Local hosts into a **Host Group** (e.g., `azurelocal-hg`).
- Create the volume(s) sized for your workload and **connect them to the Host Group** (so every node sees them).
- Configure FC **zoning** between each node's HBA WWPNs and the FlashArray target ports on both fabrics.

Confirm with your storage administrator before continuing:

| Item | Required |
| --- | --- |
| LUNs created and mapped to **all** cluster nodes | ✓ |
| Host entries created using the WWPNs from Step 2 | ✓ |
| FC zoning configured between HBAs and array target ports | ✓ |
| Consistent LUN IDs presented to all nodes | ✓ |

### Step 5: Verify MPIO and reboot

On each node, confirm the registration, then perform a **rolling reboot** to apply MPIO changes:

```powershell
mpclaim -s -d
Get-MSDSMSupportedHw
```

### Step 6: Verify SAN disks on every node

FC LUNs appear automatically after zoning and LUN masking. Run on **every** node and confirm all nodes see the **same** LUNs. Disk numbers may differ between nodes — use `UniqueId` as the authoritative identifier. The FlashArray LUNs are separate from the local S2D disks (`BusType` filters them out).

```powershell
# Rescan storage
Update-HostStorageCache

# List FC LUNs only (S2D disks have a different BusType)
Get-Disk | Where-Object BusType -eq 'Fibre Channel' |
    Select-Object Number, FriendlyName, Size, OperationalStatus, PartitionStyle, BusType |
    Format-Table -AutoSize

# Verify MPIO path count per disk
mpclaim -s -d

# Confirm UniqueId matches across all nodes
Get-Disk | Where-Object BusType -eq 'Fibre Channel' |
    Select-Object Number, SerialNumber, UniqueId | Format-Table -AutoSize
```

### Step 7: Initialize and format the disk (single node only)

Run on **one** node only. Initialize as GPT and format NTFS with a 64K allocation unit (recommended for CSV). SAN LUNs are Offline by default (`OfflineShared` policy), so bring them online first.

```powershell
$sanDisks = Get-Disk | Where-Object {
    $_.BusType -eq 'Fibre Channel' -and $_.PartitionStyle -eq 'RAW'
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

### Step 8: Add the disk to the cluster and create a CSV

After all FC disks are visible and validated, add them to the failover cluster and convert them to Cluster Shared Volumes (CSVs).

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

### Step 9: Validate multi-node access

```powershell
# Run cluster storage validation
Test-Cluster -Include Storage

# Confirm the CSV is online on all nodes
Get-ClusterSharedVolume | Select-Object Name, State, OwnerNode
```

CSVs are exposed under `C:\ClusterStorage\` on every node. Write a test file from one node and confirm it is readable from another to validate simultaneous access.

> [`Test-Cluster`](https://learn.microsoft.com/en-us/powershell/module/failoverclusters/test-cluster) / [Validate hardware for a failover cluster](https://learn.microsoft.com/en-us/windows-server/failover-clustering/create-failover-cluster)

### Step 10: Register the CSV storage path in the Azure portal

To place VMs on the SAN volume, register each SAN CSV path in Azure. Only register the **SAN** CSV paths — Azure Local manages the Storage Spaces Direct volumes (such as `Infrastructure` and `UserStorage`) automatically.

1. Sign in to the [Azure portal](https://portal.azure.com) and open your Azure Local cluster resource.
2. Go to **Settings** > **Storage path**.
3. Select **+ Add storage path**.
4. Enter the CSV path, for example `C:\ClusterStorage\Volume1`.
5. Confirm and save. Repeat for each SAN CSV.

### Step 11: Configure for VM workloads (optional)

In Windows Admin Center, the Azure portal, or via Hyper-V, create a new VM and place its VHDX on the registered SAN CSV path (or on an S2D volume, as appropriate for the workload). Start the VM and verify normal operation.

## Troubleshooting

**FC LUNs not visible after rescan**
- Verify the array maps the LUNs to **all** cluster node WWPNs (no partial presentation).
- Rescan: `Update-HostStorageCache`
- Confirm zoning: each node's HBA WWPN must be in the same zone as a FlashArray target port.
- Confirm the FlashArray Host Group has the volumes connected.
- Verify MPIO registration: `Get-MSDSMSupportedHw`

**MPIO doesn't claim disks correctly**
- Confirm the registered IDs are exactly `PURE` / `FlashArray`: `Get-MSDSMSupportedHw`
- If you registered the hardware ID *after* the LUNs were already visible, reboot the node so MPIO can re-enumerate, then `mpclaim -s -d`.

**Local S2D disks appear alongside SAN LUNs**
- This is expected in a hybrid cluster. Filter by `BusType -eq 'Fibre Channel'` to target only FlashArray LUNs; never initialize or reformat S2D pool disks.

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
- Check the FlashArray dashboard for any QoS/throttling policies.

## Additional Notes

- The Everpure Data FlashArray uses the **native Windows MSDSM** for multipathing — there is no separate DSM to install. Apply the MPIO timer settings (Step 3) consistently on every node.
- In a hybrid cluster, S2D and FlashArray volumes coexist; place each workload on the tier that best fits its capacity and performance needs.
- Each SAN LUN maps to a single CSV; size LUNs according to per-CSV capacity and IOPS needs.
- Snapshot and replication policies can be configured on the FlashArray for Azure Local CSV backup workflows.
- Only NTFS is supported for SAN-backed CSVs; ReFS is not supported for SAN-backed volumes.

## Related Articles

- [Azure Local Quick Start Guide - Disaggregated FC](../disaggregated/FC.md)
- [Enable External Storage on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/deploy/enable-external-storage)
- [Supported SAN solutions on Azure Local (Microsoft Learn)](https://learn.microsoft.com/en-us/azure/azure-local/concepts/san-requirements)
- [Everpure Data — Azure Local integration](https://support.purestorage.com/bundle/m_microsoft_platform_guide/page/Solutions/Microsoft_Platform_Guide/topics/concept/c_azure_local.html)
- [Everpure Data FlashArray MPIO Configuration for Windows Server](https://support.purestorage.com/Solutions/Microsoft_Platform_Guide/Multipath-IO_and_Storage_Settings/Setting_the_MPIO_Policy)
