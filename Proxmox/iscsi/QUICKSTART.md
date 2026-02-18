# iSCSI on Proxmox VE - Quick Start Guide

This guide provides a streamlined path to configure iSCSI storage on Proxmox VE.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [iSCSI Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official Proxmox VE and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- Proxmox VE 8.x or later
- iSCSI storage array with portal IPs and target IQN
- Dedicated storage network interfaces
- Root access to all cluster nodes

> **📖 New to iSCSI?** See the [Storage Terminology Glossary](../../common/includes/glossary.md)

> **⚠️ Same-Subnet Multipath:** If using multiple interfaces on the same subnet, configure ARP settings. See [ARP Configuration](../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath).

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

Create `/etc/multipath.conf`:

```bash
tee /etc/multipath.conf > /dev/null <<'EOF'
defaults {
    find_multipaths      off
    polling_interval     10
    path_selector        "service-time 0"
    path_grouping_policy group_by_prio
    failback             immediate
    no_path_retry        0
}

devices {
    device {
        vendor           "PURE"
        product          "FlashArray"
        path_selector    "service-time 0"
        hardware_handler "1 alua"
        path_grouping_policy group_by_prio
        prio             alua
        failback         immediate
        path_checker     tur
        fast_io_fail_tmo 10
        dev_loss_tmo     60
        no_path_retry    0
    }
}
EOF

# Restart multipathd to apply configuration
systemctl restart multipathd

# Verify multipath devices
multipath -ll
```

> **Why `find_multipaths off`?** This ensures ALL paths to storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. See [iSCSI Best Practices](./BEST-PRACTICES.md#multipath-configuration) for detailed explanation.

> **Note:** For comprehensive multipath concepts and configuration patterns, see [Multipath Concepts](../../common/includes/multipath-concepts.md).

## Step 7: Create LVM

```bash
# Find your multipath device
multipath -ll

# Example output (with recommended no_path_retry 0 configuration)
3624a93708eabcb40cc4241b202b61a7c dm-8 PURE,FlashArray
size=5.0T features='0' hwhandler='1 alua' wp=rw
`-+- policy='service-time 0' prio=50 status=active
  |- 20:0:0:254 sdb 8:16 active ready running
  |- 21:0:0:254 sdc 8:32 active ready running
  |- 22:0:0:254 sdd 8:48 active ready running
  `- 23:0:0:254 sde 8:64 active ready running

# Note: features='0' indicates no_path_retry is configured (recommended)
# If you see features='1 queue_if_no_path', update multipath.conf to use
# no_path_retry 0 to prevent APD (All Paths Down) hangs
```

In the example above the multipath device is `3624a93708eabcb40cc4241b202b61a7c` WWID of the device.  The device name will be different for each environment.  The device name will be the same for each node.  The device name can be used to create the LVM physical volume and volume group.  

```bash
# Create PV and VG
pvcreate /dev/mapper/3624a93708eabcb40cc4241b202b61a7c
vgcreate vg_iscsi /dev/mapper/3624a93708eabcb40cc4241b202b61a7c

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

---

## Next Steps

For production deployments, see [iSCSI Best Practices](./BEST-PRACTICES.md) for:
- Network design and optimization
- Multipath configuration details
- High availability with Proxmox HA
- Performance tuning
- Security best practices
- Monitoring and troubleshooting
