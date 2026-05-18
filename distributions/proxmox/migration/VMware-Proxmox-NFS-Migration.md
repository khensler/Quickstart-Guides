# VMware to Proxmox Migration via NFS Datastore (Pure Storage FlashArray)

This guide covers migrating a VMware VM to Proxmox VE when the VM resides on an NFS datastore hosted on a Pure Storage FlashArray. Because the VM data is stored as files on NFS, no block-level multipath configuration is required.

Two migration paths are documented:

- **Method A — Direct Migration**: Power off the VM, import the VMDK into Proxmox, and start the migrated VM. The source VM's NFS files are consumed and the original VMware VM can no longer run.
- **Method B — Non-Destructive Migration via Managed Directory Copy**: Use Pure Storage's managed directory copy to create an instant array-side clone of the VM's NFS directory, then import from the clone. The source VM's files remain unchanged and it can be powered back on in VMware if the migration fails.

---

## Prerequisites

### Access Requirements
- VMware vCenter or ESXi direct access with VM power management permissions
- Pure Storage FlashArray access (GUI or CLI via SSH to the array)
- SSH root access to the target Proxmox node

### Storage Requirements
- The source VM uses an NFS datastore backed by a Pure Storage FlashArray NFS file service
- The NFS export is (or can be) mounted on the Proxmox cluster
- For Method B: the NFS file service must use Pure Storage managed directories

### Encryption Limitation
**Encrypted VMs and encrypted VMDKs cannot be migrated using this method.** VMware VM encryption and per-VMDK encryption are managed by VMware's Key Management Server (KMS). The underlying VMDK data is opaque outside of the VMware environment — QEMU has no access to the decryption keys and cannot read the disk contents. Attempting to boot an encrypted VMDK in Proxmox will result in an unbootable VM or corrupt filesystem.

Before proceeding, confirm the VM and all its disks are unencrypted. See [Step 1.1](#11-gather-vm-details-from-vcenter) for how to check.

### Virtual TPM (vTPM) Consideration

VMs using a VMware virtual TPM (vTPM) can be migrated, but **in-guest features that rely on the vTPM's key hierarchy will break on first boot in Proxmox** and require remediation before the VM is shut down in VMware.

**Why keys do not carry over:**
VMware vTPM requires VM Encryption to protect its state — the `.nvram` file containing the TPM's persistent key hierarchy (Endorsement Key, Storage Root Key, and all sealed objects) is encrypted by VMware's KMS and cannot be read or imported outside of vSphere. Proxmox uses `swtpm` for software TPM emulation, which creates a completely new, empty TPM with a different key hierarchy. Any secret the guest OS sealed to the VMware vTPM cannot be unsealed by the Proxmox `swtpm`.

**What will not work on first boot in Proxmox:**
- **BitLocker (Windows)** — BitLocker seals its Volume Master Key (VMK) to the vTPM. The Proxmox `swtpm` cannot unseal it, so the boot volume will be locked. Windows will halt at the BitLocker recovery screen and require a recovery key.
- **LUKS with TPM2 enrollment (Linux)** — Systems using `clevis-tpm2`, `systemd-cryptenroll`, or similar TPM2-based LUKS unlock will fail to unseal the volume key and will drop to a recovery prompt requiring the LUKS passphrase.
- **TPM-sealed credentials and certificates** — Any application that has sealed private keys or credentials to the vTPM (Windows Hello for Business, platform attestation, etc.) will lose access to those secrets.
- **Measured Boot / remote attestation** — PCR values will differ on the new `swtpm`, breaking any attestation chains built against the VMware vTPM's measurements.

**Recommended remediation before shutting down the VM in VMware:**

- **BitLocker**: Suspend BitLocker protection on all encrypted volumes while the VM is still running in VMware. This adds a clear-text protector alongside the TPM protector, allowing Windows to boot without TPM on the first boot in Proxmox. After migration, re-enable BitLocker and it will re-seal the VMK to the Proxmox `swtpm`.
  ```
  Manage-bde -protectors -disable C:
  ```
  Repeat for each encrypted volume. Retrieve and record all BitLocker recovery keys from Active Directory, Azure AD, or MBAM before proceeding as a fallback.

- **LUKS with TPM2**: Record or escrow the LUKS passphrase before migration. After migration, re-enroll the new `swtpm` as a LUKS key slot using `systemd-cryptenroll` or `clevis`.

- **Other TPM-sealed secrets**: Identify and back up any TPM-sealed material before migration. Re-enrollment against the Proxmox `swtpm` will be required after the VM is running.

After completing remediation, add a vTPM device to the Proxmox VM before first boot:
```bash
qm set $VMID --tpmstate0 ${NFS_STORAGE}:1,version=v2.0
```

### Proxmox NFS Storage
Ensure the Pure Storage NFS export is configured as Proxmox storage. If not already done, follow the [Proxmox NFS Quickstart](../nfs/QUICKSTART.md) guide first.

---

## Step 1: Identify the Source VM

### 1.1 Gather VM Details from vCenter

Record the following before proceeding:

- **VM Name**
- **Guest OS** (Linux, Windows — determines `--ostype` in `qm create`)
- **Firmware type** (BIOS or EFI/UEFI — found under VM > Edit Settings > VM Options > Boot Options)
- **SCSI controller type** (VM > Edit Settings > Virtual Hardware > SCSI Controller > Type)
- **Network adapter type** (VM > Edit Settings > Virtual Hardware > Network Adapter > Adapter Type)
- **MAC address(es)** (for network preservation)
- **Number and sizes of virtual disks**
- **Datastore name** the VM resides on
- **Encryption status** — confirm the VM is not encrypted (vCenter shows a lock icon on encrypted VMs; individual disk encryption is visible under VM > Edit Settings > Virtual Hardware > each disk > Encryption). **Stop here if the VM or any disk is encrypted — see the Encryption Limitation in Prerequisites.**
- **vTPM** — check whether the VM has a virtual TPM device (VM > Edit Settings > Virtual Hardware — look for a TPM device). If present, read the Virtual TPM section in Prerequisites and complete all remediation steps before powering off the VM.

### 1.2 Determine SCSI Controller Mapping

The SCSI controller type in VMware must map to the equivalent Proxmox `scsihw` parameter so the guest OS boots with its existing drivers.

| VMware SCSI Controller | Proxmox `--scsihw` | Notes |
|---|---|---|
| VMware Paravirtual (PVSCSI) | `pvscsi` | Most common for modern VMs |
| LSI Logic SAS | `megasas` | Common for Windows Server VMs |
| LSI Logic Parallel | `lsi` | Legacy VMs |

> **Note:** Using the wrong `scsihw` type will cause the guest OS to fail to find its boot disk. When in doubt, `pvscsi` is correct for most VMs created in the last decade.

### 1.3 Determine Network Adapter Mapping

The network adapter type in VMware maps directly to the equivalent Proxmox model parameter. Using the same type ensures the guest OS boots with its existing network drivers.

| VMware Adapter Type | Proxmox `model=` | Notes |
|---|---|---|
| VMXNET3 | `vmxnet3` | Most common for modern VMs. Paravirtual, good performance. |
| E1000 | `e1000` | Emulated Intel Gigabit. Common for older or Windows VMs. |
| E1000E | `e1000e` | Emulated Intel PCIe Gigabit. Common for Windows Server VMs. |
| VMXNET2 | `vmxnet3` | No Proxmox equivalent — upgrade to `vmxnet3`. Guest must have the driver. |

> **Note:** Using the wrong adapter type will cause the guest OS to lose network connectivity on boot. Match the source VM's adapter type exactly. You can switch to `virtio` after the migration is confirmed working for better performance.

### 1.4 Locate the VM Directory on NFS

On the Proxmox node (where the NFS is mounted), find the VM's directory:

```bash
# List VM directories on the NFS mount
ls /mnt/pve/<your-nfs-storage-name>/

# Identify the VM folder — typically named after the VM
ls /mnt/pve/<your-nfs-storage-name>/<vm-name>/
```

You should see files like:
```
myvm.vmdk          ← VMDK descriptor (small, text file)
myvm-flat.vmdk     ← VMDK data file (full disk size)
myvm.vmx           ← VM configuration
myvm.nvram         ← BIOS/EFI settings
```

> **Note:** Proxmox imports from the **flat VMDK** (`*-flat.vmdk`), not the descriptor file. Both thin and thick-provisioned VMDKs created by ESXi use this two-file layout — thin VMDKs simply store the flat file as a sparse file on the NFS filesystem, growing as data is written. The `qm importdisk` command handles both.

---

## Step 2: Power Off the VMware VM

### 2.1 Graceful Shutdown
1. In vCenter, right-click the VM
2. Select **Power > Shut Down Guest OS**
3. Wait for the VM to fully power off (status shows "Powered Off")

### 2.2 Shutdown from Within the Guest OS

Log in to the guest and issue a shutdown command directly:

**Linux:**
```bash
shutdown -h now
```

**Windows:**
```
shutdown /s /t 0
```

### 2.3 Force Power Off (if guest tools not responding)
1. Right-click the VM
2. Select **Power > Power Off**

> **Important:** The VM must be fully powered off before proceeding. A running or suspended VM with an open VMDK will cause data corruption if the VMDK is imported while still in use.

---

## Method A: Direct Migration

Use this method when you are ready to commit to the migration and do not need to preserve the ability to roll back to VMware.

### Step 3A: Get the Next Available VMID

On the Proxmox node:

```bash
pvesh get /cluster/nextid
# Example output: 201
```

Set this as a variable for subsequent commands:

```bash
VMID=201
VM_NAME="myvm"
NFS_STORAGE="pure-nfs"         # Your Proxmox NFS storage ID
NETWORK_BRIDGE="vmbr0"         # Your Proxmox network bridge
NET_ADAPTER="vmxnet3"          # From Step 1.3 — e.g. vmxnet3, e1000, e1000e
SCSIHW="pvscsi"                # From Step 1.2
MEMORY=8192                    # MB
CORES=4
```

### Step 4A: Create the Proxmox VM Shell

Create the VM without a disk first — the disk will be imported and attached in the next step.

```bash
qm create $VMID \
    --name "$VM_NAME" \
    --memory $MEMORY \
    --cores $CORES \
    --sockets 1 \
    --cpu host \
    --scsihw $SCSIHW \
    --net0 "${NET_ADAPTER},bridge=${NETWORK_BRIDGE}" \
    --ostype l26
```

> **ostype reference:** `l26` = Linux (kernel 2.6 or newer), `win10` = Windows 10/Server 2016+, `win11` = Windows 11/Server 2022+, `other` = generic.

**For EFI VMs**, also configure OVMF:

```bash
qm set $VMID --bios ovmf
qm set $VMID --efidisk0 ${NFS_STORAGE}:1,efitype=4m,pre-enrolled-keys=0
```

**To preserve the MAC address:**

```bash
qm set $VMID --net0 "${NET_ADAPTER},bridge=${NETWORK_BRIDGE},macaddr=00:50:56:93:a0:00"
```

### Step 5A: Add the VMDK to the VM Config

QEMU can read VMDK files natively. Point the VM directly at the VMDK descriptor in its current location — no file movement required.

First, get the virtual disk size:

```bash
NFS_MOUNT="/mnt/pve/${NFS_STORAGE}"
VM_DIR="<vm-name>"           # The VM's folder name on the NFS share
VMDK_PATH="${NFS_MOUNT}/${VM_DIR}/<vm-name>.vmdk"

# Get the virtual disk size in GiB
DISK_SIZE_G=$(qemu-img info "$VMDK_PATH" | grep 'virtual size' | grep -oP '\d+(?= GiB)')
echo "Disk size: ${DISK_SIZE_G}G"
```

Then add the disk directly to the VM config file:

```bash
# Append the disk and boot order to the VM config
cat >> /etc/pve/qemu-server/${VMID}.conf << EOF
scsi0: ${VMDK_PATH},format=vmdk,size=${DISK_SIZE_G}G
boot: order=scsi0
EOF
```

**For VMs with multiple disks**, add each additional VMDK:

```bash
cat >> /etc/pve/qemu-server/${VMID}.conf << EOF
scsi1: ${NFS_MOUNT}/${VM_DIR}/<vm-name>_1.vmdk,format=vmdk,size=<N>G
EOF
```

> **Verify before running:** Two things must be correct for each additional disk:
> - **SCSI ID** — increment for each disk (`scsi1`, `scsi2`, etc.). No two disks can share the same ID.
> - **VMDK filename and location** — VMware does not guarantee a consistent naming pattern for additional disks, and disks do not have to reside in the same directory as the VM. A disk may have been added from a different datastore or directory at any point in the VM's life.
>
> The authoritative source for disk locations is the VMX file or the vSphere interface:
>
> **VMX file** — lists every disk and its path relative to the datastore:
> ```bash
> grep -i "fileName" /mnt/pve/${NFS_STORAGE}/${VM_DIR}/<vm-name>.vmx
> ```
> Look for lines like `scsi0:1.fileName = "../other-dir/disk.vmdk"` — the path is relative to the datastore root.
>
> **vSphere interface** — in vCenter, go to **VM > Edit Settings > Virtual Hardware** and expand each disk. The datastore and file path are shown under each disk's settings.
>
> Once the actual paths are confirmed, adjust the `scsi` ID and full VMDK path in the config entry accordingly.

> **Note:** Point at the VMDK descriptor file (`.vmdk`), not the flat data file (`-flat.vmdk`). QEMU reads the descriptor and locates the flat file automatically.

### Step 6A: Start the VM

**This is the end of downtime.** The VM boots directly from the VMDK in its current location while storage migration runs in the background.

```bash
qm start $VMID

# Verify running
qm status $VMID
```

### Step 7A: Live Storage Migration

With the VM running, use `qm move_disk` to migrate the disk to Proxmox-managed storage. The VM remains online throughout.

> **Format conversion:** This command converts the disk from VMDK to qcow2. VMDK is a VMware format that Proxmox supports only for compatibility during migration — it provides no Proxmox-native features. Converting to qcow2 is recommended because:
> - **Snapshots**: qcow2 supports Proxmox VM snapshots; raw and VMDK on NFS do not
> - **Thin provisioning**: qcow2 only consumes space for written data on the NFS share
> - **Proxmox management**: the disk is fully managed by Proxmox storage — visible in the GUI, movable between storage pools, and eligible for backup jobs
> - **Performance**: qcow2 on NFS has negligible overhead compared to VMDK once the VM is running natively on Proxmox
>
> **⚠️ Resource impact:** Unlike a Pure Storage array-side clone, `qm move_disk` performs a full data copy through the Proxmox host — the entire disk contents traverse the NFS network path twice (read from source, write to destination). Plan accordingly: a 500 GB disk will consume significant NFS bandwidth and Proxmox host I/O for the duration of the copy. Schedule migrations during off-peak hours or stagger multiple concurrent migrations to avoid saturating the storage network.

```bash
TARGET_STORAGE="${NFS_STORAGE}"   # Destination Proxmox NFS storage

# Remove --delete 0 or use --delete 1 to erase the source VMDK after migration
qm move_disk $VMID scsi0 $TARGET_STORAGE --format qcow2 --delete 0
```

Monitor progress in the Proxmox GUI under **Datacenter > Tasks**, or via the CLI:

```bash
pvesh get /nodes/$(hostname)/tasks --limit 5
```

When complete, the VM config is automatically updated to reference the new storage location. Verify:

```bash
qm config $VMID | grep scsi0
# Should now show: scsi0: pure-nfs:201/vm-201-disk-0.qcow2,size=100G
```

**For VMs with multiple disks**, repeat `qm move_disk` for each disk slot (`scsi0`, `scsi1`, etc.).

Proceed to [Post-Migration Steps](#post-migration-steps).

---

## Method B: Non-Destructive Migration via Managed Directory Copy

Use this method when you want to keep the source VM unchanged and runnable in VMware as a fallback. A Pure Storage managed directory copy creates an instant, space-efficient clone of the VM's directory at the array level — no data is physically copied.

### Step 3B: Identify the Managed Directory on Pure Storage

**Using Pure Storage GUI:**
1. Navigate to **File System > Managed Directories** (or **Storage > Directories** depending on Purity version)
2. Locate the directory corresponding to your NFS datastore and VM folder
3. Note the full directory path (e.g., `nfs-filesystem/proxmox-vms/myvm`)

**Using Pure Storage CLI (SSH to the array):**
```bash
# List all managed directories
puredirectory list

# Filter for the VM's directory
puredirectory list | grep -i "<vm-name>"
```

### Step 4B: Create a Snapshot of the VM Directory

**Using Pure Storage GUI:**
1. Select the managed directory
2. Click **Create Snapshot**
3. Enter a suffix (e.g., `pre-migration`)
4. Click **Create**

**Using Pure Storage CLI:**
```bash
# Create a snapshot with a meaningful suffix
puredirectory snapshot create "<filesystem>/<directory>" --suffix pre-migration

# Example:
puredirectory snapshot create "nfs-fs/proxmox-vms/myvm" --suffix pre-migration

# Verify snapshot was created
puredirectory snapshot list "<filesystem>/<directory>"
```

### Step 5B: Create a New Managed Directory from the Snapshot

This creates a new directory containing an instant copy of the VM files. The source directory and VM files are not affected.

**Using Pure Storage GUI:**
1. Navigate to the snapshot you just created
2. Click **Copy** or **Clone**
3. Enter a new directory name (e.g., `myvm-migration`)
4. Click **Copy**

**Using Pure Storage CLI:**
```bash
# Copy from snapshot to a new directory
# Source format: <filesystem>/<directory>.<snapshot-suffix>
puredirectory copy "<filesystem>/<directory>.pre-migration" "<filesystem>/<directory>-migration"

# Example:
puredirectory copy "nfs-fs/proxmox-vms/myvm.pre-migration" "nfs-fs/proxmox-vms/myvm-migration"

# Verify the new directory exists
puredirectory list | grep "myvm-migration"
```

### Step 6B: Locate the Cloned VM Files on Proxmox

The cloned directory is accessible through the same NFS mount:

```bash
# Refresh the NFS directory listing
ls /mnt/pve/${NFS_STORAGE}/myvm-migration/

# Confirm VMDK files are present
ls /mnt/pve/${NFS_STORAGE}/myvm-migration/*.vmdk
```

### Step 7B: Create the Proxmox VM and Attach from the Clone

Follow the same steps as Method A (Steps 3A–4A) to set variables and create the VM shell, then attach the VMDK from the cloned directory directly.

```bash
VMID=$(pvesh get /cluster/nextid)
VM_NAME="myvm"
NFS_STORAGE="pure-nfs"
NFS_MOUNT="/mnt/pve/${NFS_STORAGE}"
NETWORK_BRIDGE="vmbr0"
NET_ADAPTER="vmxnet3"          # From Step 1.3 — e.g. vmxnet3, e1000, e1000e
SCSIHW="pvscsi"
MEMORY=8192
CORES=4

# Create VM shell
qm create $VMID \
    --name "$VM_NAME" \
    --memory $MEMORY \
    --cores $CORES \
    --sockets 1 \
    --cpu host \
    --scsihw $SCSIHW \
    --net0 "${NET_ADAPTER},bridge=${NETWORK_BRIDGE}" \
    --ostype l26
```

> **ostype reference:** `l26` = Linux (kernel 2.6 or newer), `win10` = Windows 10/Server 2016+, `win11` = Windows 11/Server 2022+, `other` = generic.

**For EFI VMs**, also configure OVMF:

```bash
qm set $VMID --bios ovmf
qm set $VMID --efidisk0 ${NFS_STORAGE}:1,efitype=4m,pre-enrolled-keys=0
```

**To preserve the MAC address:**

```bash
qm set $VMID --net0 "${NET_ADAPTER},bridge=${NETWORK_BRIDGE},macaddr=00:50:56:93:a0:00"
```

Before adding disks to the VM config, confirm the location and filename of every disk. Disks do not have to reside in the VM's directory — a disk may have been added from a different datastore or path at any point in the VM's life. The authoritative source is the VMX file or the vSphere interface.

**VMX file** — check the cloned directory for `fileName` entries:

```bash
grep -i "fileName" ${NFS_MOUNT}/myvm-migration/<vm-name>.vmx
```

Look for lines like `scsi0:0.fileName = "myvm.vmdk"` or `scsi0:1.fileName = "../other-dir/disk.vmdk"`. Paths are relative to the datastore root, so a `../` path means the disk resides outside the VM's own directory.

**vSphere interface** — in vCenter, go to **VM > Edit Settings > Virtual Hardware** and expand each disk. The datastore and file path are shown under each disk's settings. Use the path from the original VM, then locate the equivalent file in the cloned directory structure.

Get the disk size and add the primary VMDK to the VM config:

```bash
VMDK_PATH="${NFS_MOUNT}/myvm-migration/<vm-name>.vmdk"
DISK_SIZE_G=$(qemu-img info "$VMDK_PATH" | grep 'virtual size' | grep -oP '\d+(?= GiB)')

cat >> /etc/pve/qemu-server/${VMID}.conf << EOF
scsi0: ${VMDK_PATH},format=vmdk,size=${DISK_SIZE_G}G
boot: order=scsi0
EOF
```

**For VMs with multiple disks**, add each additional VMDK confirmed from the VMX file or vSphere above:

```bash
cat >> /etc/pve/qemu-server/${VMID}.conf << EOF
scsi1: ${NFS_MOUNT}/myvm-migration/<additional-disk>.vmdk,format=vmdk,size=<N>G
EOF
```

> **Verify before running:** Increment the SCSI ID for each disk (`scsi1`, `scsi2`, etc.) — no two disks can share the same ID. Use the exact filenames confirmed from the VMX file or vSphere, not assumed naming patterns.

Start the VM — **this is the end of downtime**:

```bash
qm start $VMID
qm status $VMID
```

Then migrate the disk to Proxmox-managed storage while the VM is running:

> **Format conversion:** This command converts the disk from VMDK to qcow2. See [Step 7A](#step-7a-live-storage-migration) for the full explanation of why this conversion is recommended.

```bash
TARGET_STORAGE="${NFS_STORAGE}"   # Destination Proxmox NFS storage

# --delete 0 leaves the cloned VMDK intact so the Pure snapshot can be cleaned up normally
qm move_disk $VMID scsi0 $TARGET_STORAGE --format qcow2 --delete 0
```

The original VM files in `myvm/` are untouched. The VMware VM can be powered back on in vCenter at any point before the storage migration completes if a rollback is needed.

### Step 8B: Cleanup After Successful Migration

Once the migrated VM is confirmed working, remove the managed directory copy and snapshot from the Pure Storage array.

**Using Pure Storage GUI:**
1. Navigate to **File System > Managed Directories**
2. Delete the `myvm-migration` directory
3. Navigate to the snapshot list for `myvm` and delete the `pre-migration` snapshot

**Using Pure Storage CLI:**
```bash
# Delete the cloned directory
puredirectory delete "nfs-fs/proxmox-vms/myvm-migration"

# Delete the snapshot
puredirectory snapshot delete "nfs-fs/proxmox-vms/myvm.pre-migration"

# Verify cleanup
puredirectory list | grep "myvm"
puredirectory snapshot list "nfs-fs/proxmox-vms/myvm"
```

---

## Post-Migration Steps

After the VM is running on Proxmox, complete the following to fully optimize it.

### 1. Verify the VM Boots and is Accessible

Confirm the VM boots successfully and you can log in before making further changes.

```bash
# Check VM is running
qm status $VMID

# Monitor console for boot messages
qm terminal $VMID
```

### 2. Remove VMware Tools

VMware Tools is unnecessary on Proxmox and can cause conflicts with Proxmox guest integration.

- **Linux**: Uninstall via package manager (`apt remove open-vm-tools` or `dnf remove open-vm-tools`) or run the VMware Tools uninstaller if tools were installed from ISO
- **Windows**: Uninstall via Add/Remove Programs

### 3. Install QEMU Guest Agent

The QEMU guest agent enables Proxmox to perform clean shutdowns, freeze the filesystem for snapshots, and report guest IP addresses.

**Linux:**
```bash
# Debian/Ubuntu
apt-get install -y qemu-guest-agent
systemctl enable --now qemu-guest-agent

# RHEL/Rocky/AlmaLinux
dnf install -y qemu-guest-agent
systemctl enable --now qemu-guest-agent
```

**Windows:** Download and install from the Proxmox host ISO at `/usr/share/virtio-win/virtio-win.iso`.

After installing the guest agent, enable it in the Proxmox VM config:
```bash
qm set $VMID --agent enabled=1
```

Then reboot the VM.

### 4. Install VirtIO Drivers (Windows Only)

For Windows VMs, install VirtIO drivers from the `virtio-win.iso` (available on the Proxmox host at `/usr/share/virtio-win/virtio-win.iso`). Mount the ISO in the VM and run the installer.

### 5 & 6. Upgrade the SCSI Controller and Network Adapter to VirtIO

Switching the SCSI controller to `virtio-scsi-single` and the network adapter to `virtio` both require the VM to be powered off and each change causes a reboot. Combine them into a single maintenance window to minimise downtime.

> **Important:** Install VirtIO drivers inside the guest (step 4) before making either change. Changing the SCSI controller without the driver installed will prevent the guest from finding its boot disk.

#### Prepare: Note current disk and network config

Before shutting down, record the current disk config strings and MAC address — you will need them to apply I/O threads and preserve the MAC:

```bash
qm config $VMID | grep -E '^scsi[0-9]+:|^net[0-9]+'
```

Example output:
```
scsi0: pure-nfs:201/vm-201-disk-0.qcow2,size=100G
net0: vmxnet3=00:50:56:93:A0:00,bridge=vmbr0
```

#### Note: `--scsihw` applies to all SCSI disks

`--scsihw virtio-scsi-single` changes the controller type for the entire VM — all SCSI disks are moved to the new controller at once. There is no per-disk controller setting.

#### Note: I/O threads must be enabled per disk

`virtio-scsi-single` gives each disk its own dedicated controller so that a separate I/O thread can be assigned to it, offloading disk I/O from the main QEMU thread. However, I/O threads are **not** enabled automatically — `iothread=1` must be set explicitly on each disk after changing the controller. Without it, the main benefit of `virtio-scsi-single` over `virtio-scsi-pci` is not realised.

#### Option 1: Single maintenance window (recommended)

Make all changes in one shutdown/start cycle:

```bash
# Shut down the VM
qm shutdown $VMID

# Change SCSI controller type (applies to all SCSI disks)
qm set $VMID --scsihw virtio-scsi-single

# Enable I/O threads on each disk — repeat for scsi1, scsi2, etc. if present
# Use the full config string from the prepare step above, appending ,iothread=1
qm set $VMID --scsi0 pure-nfs:201/vm-201-disk-0.qcow2,size=100G,iothread=1

# Change network adapter type (preserve MAC address from the prepare step)
qm set $VMID --net0 "virtio,bridge=${NETWORK_BRIDGE},macaddr=<existing-mac>"

# Start the VM
qm start $VMID
```

#### Option 2: Two separate maintenance windows

Use this if you want to validate the SCSI and I/O thread changes before also changing the network adapter, or if the changes need to be approved and scheduled independently.

**Window 1 — SCSI controller and I/O threads:**

```bash
qm shutdown $VMID
qm set $VMID --scsihw virtio-scsi-single
qm set $VMID --scsi0 pure-nfs:201/vm-201-disk-0.qcow2,size=100G,iothread=1
qm start $VMID
```

**Window 2 — Network adapter:**

```bash
qm shutdown $VMID
qm set $VMID --net0 "virtio,bridge=${NETWORK_BRIDGE},macaddr=<existing-mac>"
qm start $VMID
```

### 7. Re-Enable In-Guest Encryption (if applicable)

If the VM used a vTPM in VMware and BitLocker or LUKS/TPM2 protection was suspended before migration, re-seal encryption to the Proxmox `swtpm` now that the VM is confirmed stable. Do this while the VM is running.

> **Before re-sealing:** Confirm the `--tpmstate0` device was added to the VM config (see Prerequisites — Virtual TPM). If it was not added before first boot, shut down the VM, add it now, and start the VM again before proceeding:
> ```bash
> qm set $VMID --tpmstate0 ${NFS_STORAGE}:1,version=v2.0
> ```

#### BitLocker (Windows)

BitLocker was suspended before migration, leaving a clear-text protector on the volume. Re-enabling BitLocker removes the clear-text protector and re-seals the Volume Master Key to the Proxmox `swtpm`. Run this inside the guest for each encrypted volume:

```powershell
# Verify current protector status — should show TPM and Numerical Password protectors
Manage-bde -status C:

# Re-enable BitLocker — re-seals VMK to the current (Proxmox swtpm) TPM
Manage-bde -protectors -enable C:

# Verify the clear-text protector is gone and TPM protector is active
Manage-bde -status C:
```

Repeat for each encrypted volume (`D:`, `E:`, etc.). Verify that the recovery key is backed up to Active Directory, Azure AD, or MBAM before re-sealing, as the old recovery key stored against the VMware vTPM will no longer be valid.

#### LUKS with TPM2 (Linux)

The existing TPM2 LUKS key slot was bound to the VMware vTPM's key hierarchy and is now invalid. Wipe the old slot and re-enroll the Proxmox `swtpm`.

**Using `systemd-cryptenroll`:**

```bash
# Identify the LUKS device
lsblk -f | grep crypto

# Wipe the old TPM2 slot — you will be prompted for the LUKS passphrase
systemd-cryptenroll --wipe-slot=tpm2 /dev/sdX

# Re-enroll the new swtpm as a LUKS key slot
systemd-cryptenroll --tpm2-device=auto --tpm2-pcrs=7 /dev/sdX
```

**Using `clevis`:**

```bash
# Remove the old TPM2 binding
clevis luks unbind -d /dev/sdX -s <slot-number>

# Re-bind to the new swtpm
clevis luks bind -d /dev/sdX tpm2 '{}'
```

After re-enrollment, reboot the VM to confirm the volume unlocks automatically against the Proxmox `swtpm` without requiring a passphrase.

### 8. Enable High Availability (if applicable)

If the Proxmox cluster has HA configured, enable it for the migrated VM:

```bash
# Add VM to HA
pvesh create /cluster/ha/resources --sid vm:${VMID} --state started
```

---

## Troubleshooting

### VM fails to boot — "No bootable device"

**Cause:** Disk not attached, wrong disk slot, or wrong boot order.

```bash
# Check VM config
qm config $VMID | grep -E "scsi|boot"

# Ensure boot order points to the correct disk
qm set $VMID --boot order=scsi0
```

### VM fails to boot — kernel panic or BSOD after POST

**Cause:** SCSI controller mismatch. The guest OS does not have drivers for the selected `scsihw` type.

**Solution:** Set `scsihw` to match the original VMware SCSI controller type (see [Step 1.2](#12-determine-scsi-controller-mapping)).

```bash
qm shutdown $VMID  # or force stop if frozen
qm set $VMID --scsihw pvscsi  # or megasas / lsi
qm start $VMID
```

### `qm importdisk` fails with "permission denied"

**Cause:** The VMDK file is locked by VMware or has restrictive permissions.

```bash
# Verify the VM is fully powered off in vCenter
# Check file permissions on the VMDK
ls -la /mnt/pve/${NFS_STORAGE}/<vm-dir>/

# If needed, fix permissions
chmod 644 /mnt/pve/${NFS_STORAGE}/<vm-dir>/*.vmdk
```

### NFS mount does not show VM directory

**Cause:** NFS is not mounted, or the directory is inside a managed directory not visible from the current export.

```bash
# Verify NFS is mounted
mount | grep pve

# Check storage status
pvesm status

# Re-mount NFS if needed
pvesm scan nfs <pure-storage-nfs-ip>
```

### Managed directory copy not visible on NFS

**Cause:** The cloned directory may require a new or updated NFS export, or it may be under a different path than the parent directory.

**Solution:** Verify in the Pure Storage GUI that the cloned directory is exported via the same NFS export as the source. If not, create a new NFS export for the cloned directory and add it to Proxmox storage.

### VMDK import is slow

**Cause:** Source and destination storage are on different arrays or protocols, requiring data to be copied through the Proxmox host's memory and CPU.

**Solution:** For large VMs, consider using Method B with a managed directory copy so the clone is on the same array, then import from the clone. When both source and destination are on the same Pure Storage array, the array performs the copy internally without data traveling over the network.

---

## Quick Reference

### qm Commands

```bash
# Get next available VMID
pvesh get /cluster/nextid

# Create VM shell
qm create <vmid> --name <name> --memory <MB> --cores <N> --scsihw pvscsi --net0 "vmxnet3,bridge=vmbr0" --ostype l26

# Get VMDK virtual disk size
qemu-img info /path/to/<vm>.vmdk | grep 'virtual size'

# Add VMDK to VM config at current path (no file movement)
echo "scsi0: /mnt/pve/<storage>/<vm-dir>/<vm>.vmdk,format=vmdk,size=<N>G" >> /etc/pve/qemu-server/<vmid>.conf
echo "boot: order=scsi0" >> /etc/pve/qemu-server/<vmid>.conf

# Live storage migration while VM is running
qm move_disk <vmid> scsi0 <nfs-storage-id> --format qcow2 --delete 0

# Monitor tasks
pvesh get /nodes/$(hostname)/tasks --limit 5

# Enable OVMF for EFI VMs
qm set <vmid> --bios ovmf
qm set <vmid> --efidisk0 <storage-id>:1,efitype=4m,pre-enrolled-keys=0

# Start / stop / status
qm start <vmid>
qm shutdown <vmid>
qm status <vmid>
```

### Pure Storage Managed Directory Commands

```bash
# List managed directories
puredirectory list

# Create snapshot
puredirectory snapshot create "<filesystem>/<directory>" --suffix <suffix>

# List snapshots
puredirectory snapshot list "<filesystem>/<directory>"

# Copy snapshot to new directory
puredirectory copy "<filesystem>/<directory>.<suffix>" "<filesystem>/<new-directory>"

# Delete managed directory
puredirectory delete "<filesystem>/<directory>"

# Delete snapshot
puredirectory snapshot delete "<filesystem>/<directory>.<suffix>"
```

### VMDK File Types

| File | Description |
|---|---|
| `<vm>.vmdk` | Descriptor file (text, small) — always present |
| `<vm>-flat.vmdk` | Data file — always present; sparse on NFS for thin-provisioned disks, fully allocated for thick |
| `<vm>-delta.vmdk` | Snapshot delta (only present if VM has VMware snapshots) |

> **VMware snapshots:** If the source VM has active VMware snapshots, consolidate them in vCenter before migration (**VM > Snapshots > Consolidate**). Importing delta VMDKs without consolidation will result in an incomplete disk image.
