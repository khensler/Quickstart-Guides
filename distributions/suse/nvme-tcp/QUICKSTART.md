---
layout: default
title: NVMe-TCP on SUSE/openSUSE - Quick Start Guide
---

# NVMe-TCP on SUSE/openSUSE - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on SUSE-based systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official SUSE and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- SLES 15 SP3+ or openSUSE Leap 15.3+
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

> **📖 New to NVMe-TCP?** See the [Storage Terminology Glossary]({% link _includes/glossary.md %})

## Step 1: Install NVMe Tools

```bash
sudo zypper install -y nvme-cli
nvme version
```

## Step 2: Enable Native NVMe Multipath

```bash
# Enable multipath BEFORE connecting (requires reboot to take effect)
echo 'options nvme_core multipath=Y' | sudo tee /etc/modprobe.d/nvme-tcp.conf
sudo reboot
```

## Step 3: Configure Network Interfaces

Configure dedicated storage interfaces using Wicked (SUSE default):

```bash
# First storage interface
sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_1> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_1>/24'
MTU='9000'
NAME='Storage Network 1'
EOF

# Second storage interface
sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_2> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_2>/24'
MTU='9000'
NAME='Storage Network 2'
EOF

# Apply configuration
sudo wicked ifreload all
ip addr show
```

> **⚠️ Same-Subnet Multipath:** If both interfaces are on the same subnet, configure ARP settings. See [ARP Configuration]({% link _includes/network-concepts.md %}).

## Step 4: Configure Firewall

Add storage interfaces to trusted zone (recommended for dedicated storage networks):

```bash
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_1>
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_2>
sudo firewall-cmd --reload
```

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 5: Generate Host NQN

```bash
sudo mkdir -p /etc/nvme
sudo nvme gen-hostnqn | sudo tee /etc/nvme/hostnqn
cat /etc/nvme/hostnqn
```

**Register this NQN** with your storage array's allowed hosts list.

## Step 6: Connect to Storage

Connect each host interface to each storage portal:

```bash
# Replace values: <PORTAL_IP_X>, <SUBSYSTEM_NQN>, <INTERFACE_NAME_X>, <HOST_IP_X>
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Repeat for all portal/interface combinations to create full mesh

# Verify connections
sudo nvme list-subsys
```

## Step 7: Configure IO Policy

```bash
# Create udev rule for queue-depth IO policy
sudo tee /etc/udev/rules.d/99-nvme-iopolicy.rules > /dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Step 8: Configure Persistent Connections

```bash
# Create discovery configuration
sudo tee /etc/nvme/discovery.conf > /dev/null <<EOF
-t tcp -a <PORTAL_IP_1> -s 4420
-t tcp -a <PORTAL_IP_2> -s 4420
-t tcp -a <PORTAL_IP_3> -s 4420
-t tcp -a <PORTAL_IP_4> -s 4420
EOF

# Enable autoconnect service
sudo systemctl enable --now nvmf-autoconnect.service
```

## Step 9: Create LVM Storage

```bash
# Find NVMe device
sudo nvme list
# Example: /dev/nvme0n1

# Create LVM
sudo pvcreate /dev/nvme0n1
sudo vgcreate nvme-storage /dev/nvme0n1
sudo lvcreate -L 500G -n data nvme-storage

# Format and mount (XFS recommended)
sudo mkfs.xfs /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 10: Verify

```bash
# Check multipath is enabled
cat /sys/module/nvme_core/parameters/multipath  # Should show: Y

# Check all paths
sudo nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy  # Should show: queue-depth

# Verify storage
df -h | grep nvme
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `sudo nvme list-subsys` | Show all paths and subsystems |
| `sudo nvme list` | List NVMe devices |
| `sudo nvme connect -t tcp -a <IP> -s 4420 -n <NQN>` | Connect to subsystem |
| `sudo nvme disconnect -n <NQN>` | Disconnect from subsystem |
| `sudo wicked ifreload all` | Reload network configuration |

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (AppArmor, firewall options)
- Monitoring and troubleshooting
- YaST and wicked alternatives

**Additional Resources:**
- [Common Network Concepts]({% link _includes/network-concepts.md %})
- [Troubleshooting Guide]({% link _includes/troubleshooting-common.md %})
- [Storage Terminology Glossary]({% link _includes/glossary.md %})

