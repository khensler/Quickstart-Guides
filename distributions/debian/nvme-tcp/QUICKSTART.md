---
layout: default
title: NVMe-TCP on Debian/Ubuntu - Quick Start Guide
---

# NVMe-TCP on Debian/Ubuntu - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Debian and Ubuntu systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official Debian/Ubuntu and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- Debian 11+ or Ubuntu 20.04 LTS+
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

> **📖 New to NVMe-TCP?** See the [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

## Step 1: Install NVMe Tools

```bash
sudo apt update
sudo apt install -y nvme-cli
nvme version
```

## Step 2: Enable Native NVMe Multipath

```bash
# Enable multipath BEFORE connecting (requires reboot to take effect)
echo 'options nvme_core multipath=Y' | sudo tee /etc/modprobe.d/nvme-tcp.conf
sudo reboot
```

## Step 3: Configure Network Interfaces

Configure dedicated storage interfaces using Netplan (Ubuntu/Debian 11+):

```bash
sudo tee /etc/netplan/50-storage.yaml > /dev/null <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    <INTERFACE_NAME_1>:
      addresses:
        - <HOST_IP_1>/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
    <INTERFACE_NAME_2>:
      addresses:
        - <HOST_IP_2>/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
EOF

sudo netplan apply
ip addr show
```

> **⚠️ Same-Subnet Multipath:** If both interfaces are on the same subnet, configure ARP settings. See [ARP Configuration]({{ site.baseurl }}/common/network-concepts.html).

## Step 4: Configure Firewall

Allow all traffic on storage interfaces (recommended for dedicated storage networks):

```bash
# Using UFW
sudo ufw allow in on <INTERFACE_NAME_1>
sudo ufw allow in on <INTERFACE_NAME_2>
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

# Format and mount
sudo mkfs.ext4 /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage ext4 defaults,_netdev 0 0' | sudo tee -a /etc/fstab
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
| `sudo netplan apply` | Apply network configuration |

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (AppArmor, firewall options)
- Monitoring and troubleshooting
- Netplan and interfaces alternatives

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

