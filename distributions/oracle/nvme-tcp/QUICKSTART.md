---
layout: default
title: NVMe-TCP on Oracle Linux - Quick Start Guide
---

# NVMe-TCP on Oracle Linux - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Oracle Linux.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official Oracle Linux and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- Oracle Linux 8.x or 9.x with UEK R7 (5.15+) recommended
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

> **📖 New to NVMe-TCP?** See the [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

> **⚠️ Same-Subnet Multipath:** If using multiple interfaces on the same subnet, configure ARP settings. See [ARP Configuration]({{ site.baseurl }}/common/network-concepts.html).

## Step 1: Install Packages

```bash
sudo dnf install -y nvme-cli
sudo modprobe nvme-tcp
echo "nvme-tcp" | sudo tee /etc/modules-load.d/nvme-tcp.conf
```

## Step 2: Configure Network Interfaces

```bash
# First storage interface
sudo nmcli connection add type ethernet \
    con-name storage-1 \
    ifname <INTERFACE_NAME_1> \
    ipv4.method manual \
    ipv4.addresses <HOST_IP_1>/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Second storage interface
sudo nmcli connection add type ethernet \
    con-name storage-2 \
    ifname <INTERFACE_NAME_2> \
    ipv4.method manual \
    ipv4.addresses <HOST_IP_2>/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate
sudo nmcli connection up storage-1
sudo nmcli connection up storage-2
```

## Step 3: Configure Firewall

Add storage interfaces to trusted zone (recommended for dedicated storage networks):

```bash
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_1>
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_2>
sudo firewall-cmd --reload
```

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 4: Generate Host NQN

```bash
# Check/generate host NQN
cat /etc/nvme/hostnqn || sudo nvme gen-hostnqn | sudo tee /etc/nvme/hostnqn
```

**Register this host NQN** with your storage array.

## Step 5: Discover NVMe Subsystems

```bash
# Port 8009 = Discovery Controller port
sudo nvme discover -t tcp -a <PORTAL_IP_1> -s 8009
```

## Step 6: Connect to NVMe Subsystems

```bash
# Connect via first interface
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Connect via second interface
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Verify connections
sudo nvme list-subsys
```

## Step 7: Configure IO Policy

```bash
# Set IO policy (queue-depth recommended for Pure Storage)
for ctrl in /sys/class/nvme-subsystem/nvme-subsys*/iopolicy; do
    echo "queue-depth" | sudo tee $ctrl
done

# Make persistent with udev rule
sudo tee /etc/udev/rules.d/71-nvme-io-policy.rules > /dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF
```

## Step 8: Configure Persistent Connections

```bash
# Enable nvmf-autoconnect service
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
sudo mkfs.xfs /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 10: Verify

```bash
# Check connections
sudo nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Verify storage
df -h | grep nvme
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `sudo nvme discover -t tcp -a <IP> -s 8009` | Discover subsystems (port 8009) |
| `sudo nvme connect -t tcp -a <IP> -s 4420 -n <NQN>` | Connect to subsystem (port 4420) |
| `sudo nvme disconnect -n <NQN>` | Disconnect from subsystem |
| `sudo nvme list-subsys` | List subsystems and paths |
| `cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy` | Check IO policy |

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (SELinux, firewall options)
- Monitoring and troubleshooting
- High availability considerations
- UEK vs RHCK kernel selection
- Ksplice zero-downtime updates

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

