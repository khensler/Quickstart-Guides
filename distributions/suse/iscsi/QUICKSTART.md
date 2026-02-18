# iSCSI on SUSE/openSUSE - Quick Start Guide

This guide provides a streamlined path to configure iSCSI storage on SUSE/openSUSE systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [iSCSI Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official SUSE and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- SLES 15 SP3+ or openSUSE Leap 15.3+
- iSCSI storage array with portal IPs and target IQN
- Dedicated storage network interfaces
- Root or sudo access

> **📖 New to iSCSI?** See the [Storage Terminology Glossary](../../../common/includes/glossary.md)

> **⚠️ Same-Subnet Multipath:** If using multiple interfaces on the same subnet, configure ARP settings. See [ARP Configuration](../../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath).

## Step 1: Install Packages

```bash
sudo zypper install -y open-iscsi multipath-tools
sudo systemctl enable --now iscsid multipathd
```

## Step 2: Configure Network Interfaces

Create `/etc/sysconfig/network/ifcfg-<INTERFACE_NAME_1>`:

```bash
sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_1> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_1>/24'
MTU='9000'
EOF

sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_2> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_2>/24'
MTU='9000'
EOF

# Apply configuration
sudo wicked ifreload all
```

## Step 3: Configure Firewall

Add storage interfaces to trusted zone (recommended for dedicated storage networks):

```bash
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_1>
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_2>
sudo firewall-cmd --reload
```

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 4: Configure iSCSI Initiator

```bash
# View/generate initiator name
cat /etc/iscsi/initiatorname.iscsi

# Set automatic startup
sudo sed -i 's/^node.startup = manual/node.startup = automatic/' /etc/iscsi/iscsid.conf
sudo systemctl restart iscsid
```

**Register this initiator IQN** with your storage array.

## Step 5: Create Interface Bindings

```bash
# Create and bind first interface
sudo iscsiadm -m iface -I iface0 --op=new
sudo iscsiadm -m iface -I iface0 --op=update -n iface.net_ifacename -v <INTERFACE_NAME_1>

# Create and bind second interface
sudo iscsiadm -m iface -I iface1 --op=new
sudo iscsiadm -m iface -I iface1 --op=update -n iface.net_ifacename -v <INTERFACE_NAME_2>
```

## Step 6: Discover and Login

```bash
# Discover targets
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:3260
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:3260

# Login via each interface to each portal
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface1 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface1 --login

# Set automatic login
sudo iscsiadm -m node -T <TARGET_IQN> --op=update -n node.startup -v automatic

# Verify sessions
sudo iscsiadm -m session
```

## Step 7: Configure Multipath

Create `/etc/multipath.conf`:

```bash
sudo tee /etc/multipath.conf > /dev/null <<'EOF'
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
sudo systemctl restart multipathd

# Verify multipath devices
sudo multipath -ll
```

> **Why `find_multipaths off`?** This ensures ALL paths to storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. See [iSCSI Best Practices](./BEST-PRACTICES.md#multipath-configuration) for detailed explanation.

## Step 8: Create LVM Storage

```bash
# Find multipath device
sudo multipath -ll
# Example: mpatha

# Create LVM
sudo pvcreate /dev/mapper/mpatha
sudo vgcreate iscsi-storage /dev/mapper/mpatha
sudo lvcreate -L 500G -n data iscsi-storage

# Format and mount (XFS recommended)
sudo mkfs.xfs /dev/iscsi-storage/data
sudo mkdir -p /mnt/iscsi-storage
sudo mount /dev/iscsi-storage/data /mnt/iscsi-storage

# Add to fstab
echo '/dev/iscsi-storage/data /mnt/iscsi-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 9: Verify

```bash
# Check sessions
sudo iscsiadm -m session

# Check multipath
sudo multipath -ll

# Verify storage
df -h | grep iscsi
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `sudo iscsiadm -m session` | List active iSCSI sessions |
| `sudo iscsiadm -m discovery -t sendtargets -p <IP>:3260` | Discover targets |
| `sudo iscsiadm -m node -T <IQN> -p <IP>:3260 --login` | Login to target |
| `sudo iscsiadm -m node -T <IQN> -p <IP>:3260 --logout` | Logout from target |
| `sudo multipath -ll` | Show multipath devices |
| `sudo wicked ifreload all` | Reload network configuration |

---

## Next Steps

For production deployments, see [iSCSI Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Multipath configuration details
- Security best practices (AppArmor, CHAP, firewall options)
- Monitoring and troubleshooting
- High availability considerations

**Additional Resources:**
- [Common Network Concepts](../../../common/includes/network-concepts.md)
- [Multipath Concepts](../../../common/includes/multipath-concepts.md)
- [Troubleshooting Guide](../../../common/includes/troubleshooting-common.md)
- [Storage Terminology Glossary](../../../common/includes/glossary.md)

