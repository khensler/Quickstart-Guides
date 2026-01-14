# Quick Start: Manual iSCSI Multipath Configuration

This guide shows how to manually configure iSCSI multipath on Proxmox

## Prerequisites

- Proxmox VE 9.x or later
- ISCSI storage array with:
  - Portal IP address(es) and port
  - Target IQN
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between Proxmox nodes and storage

## Step 1: Install iSCSI and Multipath Tools

```bash
apt update
apt install -y open-iscsi multipath-tools
systemctl enable --now iscsid multipathd
```

## Step 2: Create iSCSI Interface Bindings

In this step the iscsi interfaces will be created.  This is similar to portbinding on ESXI.  This will allow the multipath to use the specific interfaces for the iscsi traffic.  Replace `<INTERFACE_NAME_1>` and `<INTERFACE_NAME_2>` with your actual interface names (ens1f0np0, ens2f0np0, etc.).  Replace `<PORTAL_IP_1>` and `<PORTAL_IP_2>` with your actual portal IP addresses.  Replace `<PORT>` with your actual port (Default is 3260).  The example below assumes you have 2 portals.  If you have more or less, adjust accordingly.

```bash
# Create and bind first interface
iscsiadm -m iface -I iface-<INTERFACE_NAME_1> -o new
iscsiadm -m iface -I iface-<INTERFACE_NAME_1> -o update -n iface.net_ifacename -v <INTERFACE_NAME_1>

# Create and bind second interface
iscsiadm -m iface -I iface-<INTERFACE_NAME_2> -o new
iscsiadm -m iface -I iface-<INTERFACE_NAME_2> -o update -n iface.net_ifacename -v <INTERFACE_NAME_2>

# Verify
iscsiadm -m iface
```

## Step 3: Discover Targets

```bash
iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:<PORT>
iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:<PORT>

# List discovered targets
iscsiadm -m node
```

## Step 3: Configure Authentication (Optional)

If the target requires authentication, configure it as follows.  Replace `<TARGET_IQN>` with your actual target IQN.  Replace `<PORTAL_IP_X>` with your actual portal IP addresses.  Replace `<CHAP_USER>` and `<CHAP_PASS>` with your actual CHAP credentials.  The example below is for a single target and portal.  If you have more, repeate the process for each target and portal.

```bash
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_X> -o update -n node.session.auth.authmethod -v CHAP
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_X> -o update -n node.session.auth.username -v <CHAP_USER>
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_X> -o update -n node.session.auth.password -v <CHAP_PASS>
```

## Step 4: Set Startup Mode

For session persistence across reboots.  Replace `<PORTAL_IP_X>` with your actual portal IP addresses.  Replace `<TARGET_IQN>` with your actual target IQN.  The example below is for a single target and portal.  If you have more, repeate the process for each target and portal.

```bash
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_X> -o update -n node.startup -v automatic
```

## Step 5: Login with Interface Binding

Replace `<PORTAL_IP_X>` with your actual portal IP addresses.  Replace `<TARGET_IQN>` with your actual target IQN.  Replace `<INTERFACE_NAME_X>` with your actual interface names.  The example below is for 2 portals and 2 interfaces.  If you have more or less, adjust accordingly. By loging in with the interface binding, specific interfaces will be used for the iscsi traffic.

```bash
# Login to each portal via each interface (creates 4 paths for 2x2)
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:<PORT> -I iface-<INTERFACE_NAME_1> -l
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:<PORT> -I iface-<INTERFACE_NAME_2> -l
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:<PORT> -I iface-<INTERFACE_NAME_1> -l
iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:<PORT> -I iface-<INTERFACE_NAME_2> -l

# Verify sessions
iscsiadm -m session
```

## Step 6: Configure Multipath

DM-Multipath configuration is beyond the scope of this guide.  The example below is a basic configuration that should work in most environments.  For more information see: https://support.purestorage.com/bundle/m_linux/page/Solutions/Oracle/Oracle_on_FlashArray/library/common_content/c_recommended_dmmultipath_settings.html

## Step 7: Create LVM

```bash
# Find your multipath device
multipath -ll

Output:
3624a93708eabcb40cc4241b202b61a7c dm-8 PURE,FlashArray
size=5.0T features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
`-+- policy='service-time 0' prio=50 status=active
  |- 20:0:0:254 sdb 8:16 active ready running
  |- 21:0:0:254 sdc 8:32 active ready running
  |- 22:0:0:254 sdd 8:48 active ready running
  `- 23:0:0:254 sde 8:64 active ready running
```

In the example above the multipath device is `3624a93708eabcb40cc4241b202b61a7c` WWID of the device.  The device name will be different for each environment.  The device name will be the same for each node.  The device name can be used to create the LVM physical volume and volume group.  

```bash
# Create PV and VG
pvcreate /dev/3624a93708eabcb40cc4241b202b61a7c
vgcreate vg_iscsi /dev/3624a93708eabcb40cc4241b202b61a7c

# Verify
vgs
pvs
```

## Step 8: Add LVM Storage to Proxmox

Now that the storage is configured and available as an LVM volume group, it can be added to Proxmox.  This can be done via the GUI or CLI.  The GUI is recommended for ease of use but since the rest of the guide is CLI based the CLI based approach may be quicker.

### CLI

```bash
# Add LVM storage
pvesm add lvm iscsi-datastore \
    --vgname vg_iscsi \
    --content images,rootdir \
    --shared 1

# Verify
pvesm status
```

### GUI

Go to: Datacenter -> Storage.  Click "Add" -> "LVM".  

![Add LVM Storage](./img/disk-configuration-1.png)

Name the storage in the ID field.  Select the volume group in the Volume Group drop down.  Check the "Shared" box.  Select the appropriate Content (Disk Image, Container).  Enable the volume on other nodes by either selecting them in the Nodes drop down or by clearing the Nodes field by clicking the "x" to the right of the field.  Click "Add".

![Configure Storage](./img/disk-configuration-2.png)
