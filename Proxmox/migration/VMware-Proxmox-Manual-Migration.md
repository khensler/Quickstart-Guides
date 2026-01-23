# Manual Pure vVOL VMware to Proxmox Migration Guide

This guide walks through the complete manual process to migrate a VM from VMware vCenter to Proxmox VE using Pure Storage vVols. The migration will be to a LVM Thick volume.

## Prerequisites

### Access Requirements
- VMware vCenter access with VM power management permissions
- Pure Storage FlashArray access (GUI or CLI)
- SSH root access to all Proxmox cluster nodes
- The VM to migrate uses Pure Storage vVol storage

### Proxmox Host Group
Ensure all Proxmox nodes are configured in a Pure Storage host group with proper FC/iSCSI initiators.

### Proxmox Multipath Configuration
Ensure the dm-mulitpath is installed and configured.  multipathd should be running and configured to auto-discover and add Pure Storage LUNs (blacklisting all devices except for Pure Storage LUNs and `find_multipaths = off` is recommended).  This guide uses /dev/mapper devices for the cloned LUNs.  This guide does not cover setting up multipath for general use.  That should be done following the Proxmox and Pure Storage documentation.

### Required Packages on Proxmox Nodes
```bash
apt-get install -y sg3-utils multipath-tools
```

---

## Step 1: Identify Source VM and vVol Volumes

### 1.1 Get VM Information from vCenter
1. Log into vCenter
2. Find the VM and note:
   - VM Name
   - Number of virtual disks
   - Datastore (should be vVol-based)
   - MAC addresses (for network preservation)
   - Firmware type (BIOS or EFI)

### 1.2 Identify vVol Volume Names on Pure Storage

**Using Pure Storage GUI:**
1. Navigate to **Storage > Volumes**
2. Filter or search for volumes containing the VM name
3. The volumes with Data in the name are the vVol volumes for the VM
4. Note the volume names (format: `vvol-<vm-name>-<uuid>-<disk>`)

**Using purecli:**
```bash
# List all volumes
purevol list

# Filter by VM name pattern
purevol list | grep -i "<vm-name>"

# Get volume details including serial
purevol list --csv | grep -i "<vm-name>"
```

---

## Step 2: Shutdown VMware VM

### 2.1 Graceful Shutdown via vCenter
1. Right-click the VM in vCenter
2. Select **Power > Shut Down Guest OS**
3. Wait for the VM to fully power off

### 2.2 Alternative: Force Power Off (if guest tools not responding)
1. Right-click the VM
2. Select **Power > Power Off**

---

## Step 3: Clone vVol Volumes on Pure Storage

### 3.1 Using Pure Storage GUI

For each vVol disk:
1. Navigate to **Storage > Volumes**
2. Find the source vVol volume
3. Click the volume, then click **Copy**
4. Enter a new name: `proxmox-<vm-name>-disk-<N>` (e.g., `proxmox-myvm-disk-0`)
5. Click **Copy**
6. Repeate this for any additional data volumes

### 3.2 Using purecli

```bash
# Clone each vVol to a new volume
purevol copy <source-vvol-name> <new-volume-name>

# Example:
purevol copy "vvol-myvm-abc123-virtualDisk-0" "proxmox-myvm-disk-0"

# Get the serial of the new volume
purevol list proxmox-myvm-disk-0 --csv

# Repeat for each Datavolume
```

### 3.3 Record Clone Information

For each cloned volume, record:
- Volume name: `proxmox-myvm-disk-0`
- Serial number: (from purevol list)
- WWN: `3624a9370` + serial_lowercase
- Size in GB

---

## Step 4: Prepare Proxmox Nodes (LVM Filter and kpartx Blocking)

Before attaching the cloned LUNs to Proxmox, create filters to prevent LVM from activating volume groups and kpartx from creating partition mappings on the cloned disks.

> **Note:** Use the WWN from the **cloned** volumes (from Step 3), not the original source vVols.

> **Example WWN:** Throughout this step, `3624a93708eabcb40cc4241b208501082` is used as an example. **Replace this with your actual WWN** from Step 3 (format: `3624a9370` + lowercase serial from the cloned volume).

### 4.1 Add WWN to Filter List

We will use `/var/lib/migrator/filtered_wwns` to track all WWNs currently being migrated. This serves several purposes:

- **Concurrent migrations**: Multiple VMs can migrate at once, each with their own disks
- **Safe cleanup**: When one migration finishes, only that disk's filter is removed while others remain protected
- **Persistence**: The list survives reboots if a migration is interrupted

On **ALL** Proxmox nodes, run:
```bash
# Create directories
mkdir -p /etc/lvm/lvm.conf.d
mkdir -p /var/lib/migrator

# Add WWN to the filter list (repeat for each disk)
# This file tracks all active migration LUNs for safe cleanup later
# Replace the example WWN with your actual WWN from Step 3
echo "3624a93708eabcb40cc4241b208501082" >> /var/lib/migrator/filtered_wwns
```

### 4.2 Create LVM Filter Configuration

Create `/etc/lvm/lvm.conf.d/pure-migrator.conf`:
```bash
# Replace the example WWN with your actual WWN from Step 3
cat > /etc/lvm/lvm.conf.d/pure-migrator.conf << 'EOF'
# Filters migration LUNs to prevent LVM activation
devices {
    global_filter = [ "r|/dev/mapper/3624a93708eabcb40cc4241b208501082|", "a|.*|" ]
}
EOF
```

For multiple disks, add each WWN as a reject rule:
```bash
global_filter = [ "r|/dev/mapper/WWN1|", "r|/dev/mapper/WWN2|", "a|.*|" ]
```

### 4.3 Create Udev Rule to Block kpartx

Create `/etc/udev/rules.d/59-migrator-skip-kpartx.rules`:
```bash
# Replace the example WWN with your actual WWN from Step 3
cat > /etc/udev/rules.d/59-migrator-skip-kpartx.rules << 'EOF'
# Skip kpartx for migration LUNs to prevent partition mapping
KERNEL!="dm-*", GOTO="migrator_end"
ACTION!="add|change", GOTO="migrator_end"
ENV{DM_UUID}!="mpath-?*", GOTO="migrator_end"
ENV{DM_NAME}=="3624a93708eabcb40cc4241b208501082", ENV{DM_SUBSYSTEM_UDEV_FLAG1}="1", GOTO="migrator_end"
LABEL="migrator_end"
EOF
```

For multiple disks, add a line for each WWN before the LABEL line:
```bash
ENV{DM_NAME}=="<wwn1>", ENV{DM_SUBSYSTEM_UDEV_FLAG1}="1", GOTO="migrator_end"
ENV{DM_NAME}=="<wwn2>", ENV{DM_SUBSYSTEM_UDEV_FLAG1}="1", GOTO="migrator_end"
```

### 4.4 Reload Udev Rules

On **ALL** Proxmox nodes:
```bash
udevadm control --reload-rules
```

---

## Step 5: Attach Cloned Volumes to Proxmox Host Group

### 5.1 Using Pure Storage GUI

For each cloned volume:
1. Navigate to **Storage > Volumes**
2. Select the cloned volume
3. Click **Connected Hosts**
4. Click **Connect**
5. Select **Host Groups** tab
6. Select your Proxmox host group (e.g., `proxmox-cluster`)
7. Click **Connect**

### 5.2 Using purecli

```bash
# Connect volume to host group
purevol connect <volume-name> --hgroup <host-group-name>

# Example:
purevol connect proxmox-myvm-disk-0 --hgroup proxmox-cluster

# Verify connection
purevol listconnection proxmox-myvm-disk-0
```

---

## Step 6: SCSI Rescan on All Proxmox Nodes

On **ALL** Proxmox nodes, run:

```bash
# Using rescan-scsi-bus.sh (recommended)
rescan-scsi-bus.sh -a -r -u

# If rescan-scsi-bus.sh not found, install sg3-utils first:
apt-get install -y sg3-utils
rescan-scsi-bus.sh -a -r -u

# Alternative fallback if sg3-utils unavailable:
for host in /sys/class/scsi_host/host*/scan; do echo '- - -' > $host 2>/dev/null; done
for port in /sys/class/fc_host/host*/issue_lip; do echo 1 > $port 2>/dev/null; done
```

### 6.1 Verify Multipath Devices Appeared

```bash
# List multipath devices
multipath -ll

# Check for your WWN (use your actual WWN prefix)
ls /dev/mapper/ | grep 3624a9370

# Should see device WITHOUT partition suffixes (due to kpartx blocking):
# Example: 3624a93708eabcb40cc4241b208501082
# NOT:     3624a93708eabcb40cc4241b208501082-part1
```

### 6.2 Verify No LVM VGs Activated

```bash
# Should NOT show VGs from source VM
vgs

# Should NOT show source VM's LVs
lvs
```

---

## Step 7: Create Proxmox VM

### 7.1 Get Next Available VMID

```bash
pvesh get /cluster/nextid
# Returns next available VMID, e.g., 108
```

### 7.2 Create VM with Raw Disk

```bash
# Create VM with basic settings
# Replace these example values with your actual values
VMID=108                                      # From Step 7.1
VM_NAME="myvm"                                # Your VM name
NODE="proxmox-02"                             # Target Proxmox node
NETWORK="vmbr0"                               # Your network bridge
WWN="3624a93708eabcb40cc4241b208501082"       # Your actual WWN from Step 3
SCSIHW="pvscsi"                               # See Step 7.2.1 for mapping

# Create VM
# --ostype values: l26 = Linux 2.6+, win10 = Windows 10/Server 2016+, win11 = Windows 11/Server 2022
qm create $VMID \
    --name "$VM_NAME" \
    --memory 8192 \
    --cores 4 \
    --sockets 1 \
    --cpu host \
    --scsihw $SCSIHW \
    --scsi0 "/dev/mapper/${WWN}" \
    --net0 "vmxnet3,bridge=${NETWORK}" \
    --ostype l26 \
    --boot order=scsi0
```

> **ostype reference:** `l26` = Linux (kernel 2.6 or newer), `win10` = Windows 10/Server 2016+, `win11` = Windows 11/Server 2022+, `other` = generic. This optimizes QEMU settings for the guest OS. Match this to the source VM's OS.

#### 7.2.1 SCSI Controller Type Mapping

The `--scsihw` parameter specifies the SCSI controller type. **Match this to your source VMware VM's SCSI controller** to ensure the guest OS has compatible drivers already installed.

**VMware to Proxmox SCSI Controller Mapping:**

| VMware SCSI Controller | Proxmox `--scsihw` | Notes |
|------------------------|-------------------|-------|
| VMware Paravirtual (PVSCSI) | `pvscsi` | **Most common for modern VMs.** Best performance. Requires PVSCSI driver in guest. |
| LSI Logic SAS | `megasas` | Common for Windows Server VMs. Uses MegaRAID SAS driver. |
| LSI Logic Parallel | `lsi` | Legacy. Uses LSI 53C895A driver. |
| BusLogic Parallel | `lsi` | Very old VMs. LSI is closest match. |

**How to find your source VM's SCSI controller in VMware:**

```bash
# Using govc (VMware CLI)
govc device.info -vm "VM_NAME" | grep -A5 "SCSI controller"

# Or in vCenter UI:
# VM → Edit Settings → Virtual Hardware → SCSI Controller → Type
```

**What happens if you use the wrong controller?**
- **Wrong controller = guest won't boot** (no driver for the disk controller)
- The guest OS must have drivers for the SCSI controller type you choose
- VMware VMs with PVSCSI have the `pvscsi` driver installed, so use `pvscsi` in Proxmox
- If unsure and the source was a modern VMware VM, `pvscsi` is the safest choice

**Available Proxmox SCSI controller types:**

| Proxmox `scsihw` | Description | Use Case |
|------------------|-------------|----------|
| `pvscsi` | VMware Paravirtual SCSI | VMware migrations (most common.  Can be used for migrations but should be changed to virtio-scsi-single after migration) |
| `virtio-scsi-single` | VirtIO SCSI (single queue per disk) | New Linux VMs with virtio drivers. Recommended for general use. |
| `virtio-scsi-pci` | VirtIO SCSI (multi-queue) | Linux VMs |
| `megasas` | LSI MegaRAID SAS | Windows servers, LSI SAS migrations |
| `lsi` | LSI 53C895A | Legacy VMs, broad compatibility |
| `lsi53c810` | LSI 53C810 | Very old systems |

### 7.3 For EFI VMs (from VMware EFI guests)

```bash
# Add EFI disk and BIOS type
qm set $VMID --bios ovmf
# Change "local-lvm" to your destination storage.
qm set $VMID --efidisk0 local-lvm:1,efitype=4m,pre-enrolled-keys=0
```

### 7.4 Preserve MAC Address (Optional but Recommended)

```bash
# Set MAC address from source VM.  Replace the example MAC with your actual MAC from the source VM.
# Replace the example network adapter type with the actual type from the source VM or the desired type for the new VM.  The example uses vmxnet3.  Other common types are e1000 and virtio.
qm set $VMID --net0 "vmxnet3,bridge=${NETWORK},macaddr=00:50:56:93:a0:00"
```

### 7.5 Multiple Disks

For VMs with multiple disks, add each disk:
```bash
qm set $VMID --scsi1 "/dev/mapper/${WWN2}"
qm set $VMID --scsi2 "/dev/mapper/${WWN3}"
```

---

## Step 8: Start Proxmox VM

```bash
qm start $VMID

# Verify running
qm status $VMID
```

At this point, the VM is running from the raw multipath devices. The next step migrates the disks to Proxmox-managed storage.

## Step 9: Validate VM Configuration

Before proceeding, validate the VM configuration and ensure it is running properly. Verify the VM is running and all disks are detected and mounted. Verify the network is working and the VM has IP connectivity. Since the PCIID of the network controller has changed from the VMware VM, the VM may have a new IP address or may need to be reconfigured. If the VM is not running properly, resolve any issues before proceeding.

---

## Step 9: Live Migrate Disks to Proxmox Storage

This step performs a live block copy from the raw /dev/mapper device to LVM-backed Proxmox storage using QEMU's QMP interface.  The Proxmox GUI/API is not able to preform this operation due to the direct mapping of the storage in the VM config.  An error will occur if attempted stating the system is unable to parse the volume ID as Proxmox expects the volume ID to be in the format of `storage:vm-<vmid>-disk-<N>`.

### 9.1 Identify Target Storage VG

```bash
# Check storage.cfg for your target storage
# Replace "iscsi" with your actual storage ID
cat /etc/pve/storage.cfg | grep -A5 "lvm: iscsi"

# Note the vgname, e.g., "proxmox-cluster-pool"
```

### 9.2 Get Source Disk Size

```bash
blockdev --getsize64 /dev/mapper/${WWN}
# Returns size in bytes, e.g., 107374182400 (100GB)

# Convert to MB for LV creation
SIZE_MB=$((107374182400 / 1024 / 1024))
```

### 9.3 Create Target LV

```bash
# This is the targer VG for the destination VM disk
VGNAME="proxmox-cluster-pool"
LV_NAME="vm-${VMID}-disk-0"

lvcreate -L ${SIZE_MB}M -n ${LV_NAME} ${VGNAME} -y -Wy

# Verify LV exists
lvs ${VGNAME}/${LV_NAME}
```

### 9.4 Connect to QMP Socket

The VM must be running. Connect to its QMP socket:

```bash
# Verify socket exists
ls -la /run/qemu-server/${VMID}.qmp
```

### 9.5 Perform Live Mirror via QMP

QMP requires a persistent session - all commands must be sent within the same connection. Use `socat` in interactive mode to maintain the session.

#### 9.5.1 Set Variables

```bash
# Replace these example values with your actual values
VMID=108                                      # Your VM ID from Step 7
WWN="3624a93708eabcb40cc4241b208501082"       # Your actual WWN from Step 3
VGNAME="proxmox-cluster-pool"        # Your target LVM volume group
LV_NAME="vm-${VMID}-disk-0"
LV_PATH="/dev/${VGNAME}/${LV_NAME}"
QMP_SOCK="/run/qemu-server/${VMID}.qmp"
```

#### 9.5.2 Connect to QMP (Interactive Session)

Start an interactive session that stays open:

```bash
socat - UNIX-CONNECT:${QMP_SOCK}
```

You'll see a greeting message like:
```json
{"QMP": {"version": {...}, "capabilities": ["oob"]}}
```

> **Note:** Keep this session open for all subsequent commands. Each command is typed/pasted and you'll see the response.

#### 9.5.3 Negotiate Capabilities

Type this command (required before any other commands):

```json
{"execute": "qmp_capabilities"}
```

Expected response: `{"return": {}}`

#### 9.5.4 Query Named Block Nodes

Query the block device structure to identify the node names needed for the mirror operation.

```json
{"execute": "query-named-block-nodes"}
```

**Understanding the Output:**

QEMU creates a multi-layer block device stack. You'll see multiple entries for the same physical device with **3 layers**:

```
Layer 1 (Top):    drive-scsi0          [throttle driver]  <- Use for "device" parameter
                       |
Layer 2 (Middle): ffa5d4038f11ff...    [raw driver]       <- Use for "replaces" parameter
                       |
Layer 3 (Bottom): efa5d4038f11ff...    [host_device driver] -> /dev/mapper/3624a9370...
```

**Identify the three node names:**

1. **Top throttle node** - Look for:
   - `"node-name": "drive-scsi0"` (or `drive-virtio0`, `drive-sata0`, etc.)
   - `"drv": "throttle"`
   - `"backing_file_depth": 1`
   - Has a `"children"` array

2. **Child below throttle (raw driver)** - Look in the throttle node's `children` array:
   - Find the entry with `"child": "file"`
   - Note the `"node-name"` (will be a hash like `ffa5d4038f11ff4c1cbb20961716981`)
   - This node will have `"drv": "raw"`

3. **Bottom host_device node** - Look for:
   - `"drv": "host_device"`
   - `"file": "/dev/mapper/3624a9370..."` (your source device)
   - `"children": []` (empty array)
   - Note the `"node-name"` (will be a hash like `efa5d4038f11ff4c1cbb20961716981`)

**Example from output:**

Top throttle node:
```json
{
  "node-name": "drive-scsi0",
  "drv": "throttle",
  "backing_file_depth": 1,
  "children": [
    {
      "node-name": "ffa5d4038f11ff4c1cbb20961716981",
      "child": "file"
    }
  ],
  ...
}
```

Child below throttle (raw driver):
```json
{
  "node-name": "ffa5d4038f11ff4c1cbb20961716981",
  "drv": "raw",
  "backing_file_depth": 0,
  "children": [
    {
      "node-name": "efa5d4038f11ff4c1cbb20961716981",
      "child": "file"
    }
  ],
  "file": "/dev/mapper/3624a93708eabcb40cc4241b208501082"
}
```

Bottom host_device node:
```json
{
  "node-name": "efa5d4038f11ff4c1cbb20961716981",
  "drv": "host_device",
  "backing_file_depth": 0,
  "children": [],
  "file": "/dev/mapper/3624a93708eabcb40cc4241b208501082"
}
```

**Write down these three node names - you'll need them in the following steps.**

**Common top-level device names:**

| VM Disk Type | Top-Level Node Name |
|--------------|---------------------|
| VirtIO-SCSI disk 0 | `drive-scsi0` |
| VirtIO-SCSI disk 1 | `drive-scsi1` |
| VirtIO-BLK disk 0 | `drive-virtio0` |
| SATA disk 0 | `drive-sata0` |
| IDE disk 0 | `drive-ide0` |

#### 9.5.5 Add Target Block Device

Add the target LVM volume as a block device node.

**Replace the filename with your actual LVM path:**

```json
{"execute": "blockdev-add", "arguments": {"driver": "raw", "node-name": "mirror-target-scsi0", "file": {"driver": "host_device", "filename": "/dev/proxmox-cluster-pool/vm-108-disk-0"}}}
```

**Parameters explained:**
- `"driver": "raw"` - No format, just raw block device
- `"node-name": "mirror-target-scsi0"` - Temporary name for the target (must match disk number, e.g., `mirror-target-scsi0`, `mirror-target-scsi1`)
- `"filename"` - Path to your LVM logical volume (from step 9.3)

Expected response: `{"return": {}}`

#### 9.5.6 Start the Block Mirror

Start the live block mirror operation using the node names from step 9.5.4.

**You need TWO node names from step 9.5.4:**
1. **Top throttle node** (e.g., `drive-scsi0`) - for the `device` parameter
2. **Child below throttle** (e.g., `ffa5d4038f11ff...`) - for the `replaces` parameter

```json
{"execute": "blockdev-mirror", "arguments": {"job-id": "mirror-scsi0", "device": "drive-scsi0", "target": "mirror-target-scsi0", "sync": "full", "replaces": "ffa5d4038f11ff4c1cbb20961716981"}}
```

**Parameters explained:**
- `"job-id": "mirror-scsi0"` - Unique identifier for this mirror job (you choose this)
- `"device": "drive-scsi0"` - **Top throttle node** from step 9.5.4
- `"target": "mirror-target-scsi0"` - Node name you created in step 9.5.5
- `"sync": "full"` - Copy all data (full synchronization)
- `"replaces": "ffa5d4038f11ff..."` - **Child below throttle (raw driver)** from step 9.5.4

**Critical:** The `replaces` parameter must be the **child node below the throttle** (the one with `"drv": "raw"`), NOT the bottom host_device node.

Expected response: `{"return": {}}`

#### 9.5.7 Monitor Mirror Progress

Run this command repeatedly to check progress:

```json
{"execute": "query-block-jobs"}
```

Output shows progress:
```json
{"return": [{"device": "mirror-scsi0", "len": 107374182400, "offset": 53687091200, "ready": false, ...}]}
```

- Calculate percentage: `offset / len * 100`
- Wait until `"ready": true` appears

#### 9.5.8 Complete the Mirror (when ready=true)

When the mirror job shows `"ready": true`, complete the switchover:

```json
{"execute": "block-job-complete", "arguments": {"device": "mirror-scsi0"}}
```

**Parameters explained:**
- `"device": "mirror-scsi0"` - The job-id from step 9.5.6

Expected response: `{"return": {}}`

Wait a few seconds for the job to finish.

#### 9.5.9 Verify Job Completed

Verify the mirror job has completed:

```json
{"execute": "query-block-jobs"}
```

Should return: `{"return": []}` (empty array means no jobs running).

**The VM is now using the target device (LVM volume).**

#### 9.5.10 Verify Source Nodes Were Replaced (Optional)

You can optionally verify that the `replaces` parameter worked correctly by querying the block nodes again:

```json
{"execute": "query-named-block-nodes"}
```

Look for the `drive-scsi0` node. You should see:
- The `children` array now points to `mirror-target-scsi0` instead of the old source node
- The `file` field shows the target device path (e.g., `/dev/nvme-tcp/vm-105-disk-0`)
- The old source nodes (e.g., `ffa5d4038f11ff...` and `efa5d4038f11ff...`) no longer exist

**Example of successful replacement:**
```json
{
  "node-name": "drive-scsi0",
  "drv": "throttle",
  "children": [{"node-name": "mirror-target-scsi0", "child": "file"}],
  "file": "json:{...\"filename\": \"/dev/nvme-tcp/vm-105-disk-0\"...}"
}
```

**What the `replaces` parameter did:**
- Automatically swapped the source node with the target node in the block device graph
- Deleted the old source nodes (`ffa5d4038f11ff...` and `efa5d4038f11ff...`)
- Released file descriptors on the old source device
- The throttle node now points directly to the target device

#### 9.5.11 Exit QMP Session

Exit the socat session:

Press `Ctrl+C`

#### 9.5.12 Verify Device Released

In a separate terminal (outside the QMP session):

```bash
# Verify device is released - should show Open count: 0
dmsetup info ${WWN} | grep "Open count"
```

If the open count is 0, the source device has been successfully released and the VM is now running entirely on the target LVM volume.

### 9.6 Update VM Configuration

After the mirror completes, update the VM config to reference the LVM storage instead of the raw device:

```bash
# Edit VM config
nano /etc/pve/qemu-server/${VMID}.conf

# Change the scsi0 line from (example WWN shown):
#   scsi0: /dev/mapper/3624a93708eabcb40cc4241b208501082
# To (use your storage name and LV name):
#   scsi0: iscsi:vm-108-disk-0,size=100G
```

Where `iscsi` is your Proxmox storage name and `vm-108-disk-0` is the LV name you created in Step 9.3.

---

## Step 10: Cleanup

After the live mirror completes and the VM config is updated, clean up the temporary resources.

### 10.1 Verify Device is No Longer in Use

```bash
# Check open count - should be 0
dmsetup info ${WWN} | grep "Open count"

# If still in use, identify what's holding it:
fuser -v /dev/mapper/${WWN}
lsof /dev/mapper/${WWN}
```

### 10.2 Remove Multipath Device from All Nodes

On **ALL** Proxmox nodes:

```bash
# Remove kpartx partition mappings (if any exist)
kpartx -d /dev/mapper/${WWN}

# Deactivate any LVM VGs on the device (if any were activated)
# First identify VGs:
pvs /dev/mapper/${WWN}*
# Then deactivate:
vgchange -an <vg-name>

# Remove multipath device
multipath -f ${WWN}

# Verify device is gone
ls /dev/mapper/ | grep ${WWN}  # Should return nothing
```

### 10.3 Detach Volume from Host Group on Pure Storage

**Using Pure Storage GUI:**
1. Navigate to **Storage > Volumes**
2. Select the cloned volume
3. Click **Connected Hosts**
4. Find the host group connection
5. Click the **X** to disconnect

**Using purecli:**
```bash
purevol disconnect <volume-name> --hgroup <host-group-name>

# Example:
purevol disconnect proxmox-myvm-disk-0 --hgroup proxmox-cluster

# Verify disconnected
purevol listconnection proxmox-myvm-disk-0
```

### 10.4 Delete Cloned Volume from Pure Storage

**Using Pure Storage GUI:**
1. Navigate to **Storage > Volumes**
2. Select the cloned volume
3. Click **Destroy** (moves to Destroyed Volumes)
4. Optionally, go to **Destroyed Volumes** and **Eradicate** to permanently remove

**Using purecli:**
```bash
# Destroy volume (moves to destroyed state)
purevol destroy <volume-name>

# Eradicate (permanently delete)
purevol eradicate <volume-name>

# Example:
purevol destroy proxmox-myvm-disk-0
purevol eradicate proxmox-myvm-disk-0
```

### 10.5 Remove LVM Filter and Udev Rules

On **ALL** Proxmox nodes:

```bash
# Remove WWN from filter list
grep -v "^${WWN}$" /var/lib/migrator/filtered_wwns > /tmp/filtered_wwns.tmp
mv /tmp/filtered_wwns.tmp /var/lib/migrator/filtered_wwns

# If filter list is now empty, remove the config files:
if [ ! -s /var/lib/migrator/filtered_wwns ]; then
    rm -f /etc/lvm/lvm.conf.d/pure-migrator.conf
    rm -f /etc/udev/rules.d/59-migrator-skip-kpartx.rules
    udevadm control --reload-rules
fi

# If other WWNs remain, rebuild the filter files manually
# (See Step 2 for format)
```

---

## Verification

### Verify VM is Running on Proxmox Storage

```bash
# Check VM config shows storage syntax
cat /etc/pve/qemu-server/${VMID}.conf | grep scsi

# Output should be like:
# scsi0: iscsi:vm-108-disk-0,size=100G
```

### Verify LV Exists and is Active

```bash
lvs | grep vm-${VMID}
```

### Test Proxmox GUI Migration

After successful migration, you should be able to use the Proxmox GUI to:
1. Move the VM between nodes
2. Move disks between storage pools
3. Take snapshots (if avilable)

---

## Post-Migration Steps

Additional steps to take after migration to fully optimize the VM.  These changes require installation of drivers, configuration changes, and a reboot of the VM.

### 1. Remove VMware Tools

VMware Tools can cause issues with Proxmox.  It is recommended to remove VMware Tools and reboot the VM.

### 2. Install virtio drivers and qemu-guest-agent

The virtio drivers are much more efficient than the emulated devices.  The qemu-guest-agent is required for Proxmox to be able to manage the VM (shutdown, reboot, etc.) and for the guest to be able to mount ISOs and have proper time sync.

#### 2.1 virtio drivers

Download the virtio drivers from the Proxmox host to a local directory on the guest.  The drivers are located in /usr/share/virtio-win/virtio-win.iso on the Proxmox host.  Mount the ISO and install the drivers.  A reboot may be required. 

#### 2.2 qemu-guest-agent

The qemu-guest-agent is available in the package manager of most Linux distributions and can be downloaded from the Proxmox host.  The package is called qemu-guest-agent.  Once installed, the service should be enabled and started.  The VM will need to be rebooted for the agent to be available.  While rebooting the VM should be configured in Proxmox to enable the guest agent.

### 3. Change the SCSI controller to virtio-scsi-single

The pvscsi controller can be used but virtio-scsi-single is recommended for Linux VMs.  Windows VMs can use the megasas controller.

### 4. Change the network adapter to virtio

The vmxnet3 adapter can be used but virtio is recommended for both Windows and Linux VMs.

### 5. Enable HA for the VM

HA should be enabled for the VM after the migration as Proxmox does not do this by default.  This can be done in the Proxmox GUI or CLI.  The VM should be configured in Proxmox to enable HA.

---

## Troubleshooting

### Device has open count > 0 after mirror

**Cause**: kpartx created partition mappings or LVM activated VGs.

**Solution**:
```bash
# Check what's holding device open
dmsetup ls | grep ${WWN}

# If partition mappings exist:
kpartx -d /dev/mapper/${WWN}

# If LVM VGs are active:
vgs  # identify VG
vgchange -an <vg-name>
```

### Mirror job not starting

**Cause**: QMP socket not found or drive name mismatch.

**Solution**:
```bash
# Verify VM is running on this node
qm status ${VMID}

# Check QMP socket exists
ls /run/qemu-server/${VMID}.qmp

# Query actual drive names via QMP
# The drive is typically "drive-scsi0" for scsi0 disk
```

### multipath -f fails with "in use"

**Cause**: Something still has the device open.

**Solution**:
1. Check for LVM: `pvs /dev/mapper/${WWN}*`
2. Check for kpartx: `ls /dev/mapper/ | grep ${WWN}`
3. Check processes: `fuser -v /dev/mapper/${WWN}`
4. If udev-workers are stuck, you may need to reboot the node

### Volume connection fails on Pure Storage

**Cause**: Host group doesn't exist or initiators not configured.

**Solution**:
- Verify host group exists in Pure Storage
- Verify all Proxmox node initiators (FC WWPN or iSCSI IQN) are in the host group

---

## Quick Reference: WWN Construction

Example (replace with your actual serial from Pure Storage):
```
Pure Volume Serial: 8EABCB40CC4241B208501082           <- Get this from Pure Storage GUI or purecli
Pure NAA prefix:    3624a9370                          <- Always this prefix for Pure Storage
WWN:                3624a93708eabcb40cc4241b208501082  <- prefix + lowercase(serial)
Multipath device:   /dev/mapper/3624a93708eabcb40cc4241b208501082
```

## Quick Reference: purecli Commands

```bash
# List volumes
purevol list

# Copy/clone volume
purevol copy <source> <dest>

# Connect to host group
purevol connect <volume> --hgroup <group>

# Disconnect from host group
purevol disconnect <volume> --hgroup <group>

# Destroy volume
purevol destroy <volume>

# Eradicate volume (permanent)
purevol eradicate <volume>

# List connections
purevol listconnection <volume>
```

## Quick Reference: QMP Commands

```json
// Negotiate capabilities (required first)
{"execute": "qmp_capabilities"}

// Query block nodes
{"execute": "query-named-block-nodes"}

// Add target block device
{"execute": "blockdev-add", "arguments": {"driver": "raw", "node-name": "target", "file": {"driver": "host_device", "filename": "/dev/vg/lv"}}}

// Start mirror
{"execute": "blockdev-mirror", "arguments": {"job-id": "mirror-scsi0", "device": "drive-scsi0", "target": "target", "sync": "full", "replaces": "source-node"}}

// Query job progress
{"execute": "query-block-jobs"}

// Complete mirror when ready
{"execute": "block-job-complete", "arguments": {"device": "mirror-scsi0"}}

// Delete orphaned source node
{"execute": "blockdev-del", "arguments": {"node-name": "source-node"}}
```


