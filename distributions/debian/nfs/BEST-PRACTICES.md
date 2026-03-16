---
layout: default
title: NFS on Debian/Ubuntu - Best Practices Guide
---

# NFS on Debian/Ubuntu - Best Practices Guide

Comprehensive best practices for deploying NFS storage on Debian/Ubuntu systems in production environments.

> **Related Guides:** For block storage alternatives, see:
> - [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md)
> - [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md)

---

{% include bestpractices/disclaimer-debian.md %}

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Debian/Ubuntu-Specific Considerations](#debianubuntu-specific-considerations)
- [Network Design](#network-design)
- [NFS Configuration](#nfs-configuration)
- [Performance Optimization](#performance-optimization)
- [Security Best Practices](#security-best-practices)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Reference Architecture

A production-grade NFS deployment consists of:

- **Debian/Ubuntu Hosts**: Multiple hosts with redundant network connectivity
- **Dedicated Storage Network**: Isolated network for NFS traffic
- **NFS Storage Array**: Everpure FlashArray with NFSv4.1 support
- **Redundant Network Paths**: Bonded NICs for failover

### NFS Virtual IP (VIP) and Controller Failover

Everpure FlashArray uses a **Virtual IP (VIP)** for NFS services:

1. **Single Active Controller**: The NFS VIP is hosted on one controller at a time
2. **Automatic Failover**: If the active controller fails, the VIP migrates to the standby
3. **Client Transparency**: NFS clients connect to the VIP—failover is transparent
4. **TCP Session Recovery**: NFSv4.1 supports session recovery after failover

---

## Debian/Ubuntu-Specific Considerations

### Supported Versions

| Distribution | Kernel | NFS Support |
|--------------|--------|-------------|
| Ubuntu 24.04 | 6.8+ | NFSv4.1, nconnect supported |
| Ubuntu 22.04 | 5.15+ | NFSv4.1, nconnect supported |
| Ubuntu 20.04 | 5.4+ | NFSv4.1, nconnect supported |
| Debian 12 | 6.1+ | NFSv4.1, nconnect supported |
| Debian 11 | 5.10+ | NFSv4.1, nconnect supported |

### Package Installation

```bash
# Update and install
sudo apt update
sudo apt install -y nfs-common

# Verify installation
dpkg -l | grep nfs-common

# Check NFS support
cat /proc/filesystems | grep nfs
```

---

## Network Design

### Network Bonding with Netplan (Ubuntu)

```yaml
# /etc/netplan/01-storage-bond.yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    eth1:
      mtu: 9000
    eth2:
      mtu: 9000
  bonds:
    bond0:
      interfaces: [eth1, eth2]
      mtu: 9000
      addresses: [10.100.1.101/24]
      parameters:
        mode: 802.3ad
        lacp-rate: fast
        mii-monitor-interval: 100
        transmit-hash-policy: layer3+4
```

```bash
# Apply configuration
sudo netplan apply

# Verify
cat /proc/net/bonding/bond0
```

### Network Bonding with ifupdown (Debian)

```bash
# /etc/network/interfaces
auto eth1
iface eth1 inet manual
    bond-master bond0
    mtu 9000

auto eth2
iface eth2 inet manual
    bond-master bond0
    mtu 9000

auto bond0
iface bond0 inet static
    address 10.100.1.101/24
    bond-slaves none
    bond-mode 802.3ad
    bond-miimon 100
    bond-xmit-hash-policy layer3+4
    mtu 9000
```

### Understanding LACP Load Balancing

LACP uses hash-based distribution—there's no guarantee of balanced traffic:

- Each flow (source/dest IP+port) uses a single link
- Single NFS mount may use only one link
- Use `nconnect` to create multiple TCP connections that may hash to different links

### Firewall Configuration (UFW)

```bash
# Allow outbound NFS
sudo ufw allow out to any port 2049 proto tcp
sudo ufw allow out to any port 111 proto tcp

# If strict incoming rules needed
sudo ufw allow from <NFS_SERVER_IP> to any port 2049

# Verify
sudo ufw status verbose
```

---

## NFS Configuration

### Mount Options

**Recommended mount options:**

| Option | Value | Description |
|--------|-------|-------------|
| `vers` | `4.1` | NFSv4.1 for improved locking |
| `nconnect` | `4-8` | Multiple TCP connections |
| `noatime` | — | Don't update access times |
| `nodiratime` | — | Don't update directory access times |
| `_netdev` | — | Wait for network before mounting |

### Persistent Mount via fstab

```bash
# Add to /etc/fstab
<NFS_SERVER_IP>:/data/debian /mnt/pure-nfs nfs4 vers=4.1,nconnect=4,noatime,nodiratime,_netdev 0 0
```

### Persistent Mount via autofs

```bash
# Install autofs
sudo apt install -y autofs

# Configure /etc/auto.master
echo '/mnt/nfs /etc/auto.nfs --timeout=300' | sudo tee -a /etc/auto.master

# Configure /etc/auto.nfs
echo 'pure-nfs -fstype=nfs4,vers=4.1,nconnect=4,noatime,nodiratime <NFS_SERVER_IP>:/data/debian' | sudo tee /etc/auto.nfs

# Enable autofs
sudo systemctl enable --now autofs
```

---

## Performance Optimization

### nconnect for Improved Throughput

The `nconnect` option creates multiple TCP connections per mount:

| Network Speed | nconnect Value |
|---------------|----------------|
| 10 GbE | 2-4 |
| 25 GbE | 4-8 |
| 100 GbE | 8-16 |

**Verify nconnect:**
```bash
mount | grep nconnect
cat /proc/fs/nfsfs/servers
```

### Kernel Tuning

```bash
cat > /etc/sysctl.d/99-nfs-tuning.conf << 'EOF'
# NFS performance tuning
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.core.rmem_default = 1048576
net.core.wmem_default = 1048576
net.ipv4.tcp_rmem = 4096 1048576 16777216
net.ipv4.tcp_wmem = 4096 1048576 16777216
EOF

sudo sysctl -p /etc/sysctl.d/99-nfs-tuning.conf
```

---

## Security Best Practices

### Network Isolation

- Use dedicated VLANs for NFS traffic
- Configure UFW rules to restrict access
- Never expose NFS to untrusted networks

### AppArmor Configuration

AppArmor is enabled by default on Ubuntu. Check status:

```bash
# Check AppArmor status
sudo aa-status

# If NFS access is blocked, check logs
sudo journalctl | grep apparmor | grep DENIED
```

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check mount status
mount | grep nfs
df -h | grep nfs

# NFS statistics
nfsstat -c

# Check for errors
dmesg | grep -i nfs
journalctl -u nfs-client.target
```

### Automated Monitoring

```bash
#!/bin/bash
# /usr/local/bin/check-nfs-health.sh
MOUNT_POINT="/mnt/pure-nfs"

if ! mountpoint -q "$MOUNT_POINT"; then
    echo "ERROR: NFS not mounted"
    exit 1
fi

if ! ls "$MOUNT_POINT" > /dev/null 2>&1; then
    echo "ERROR: NFS not accessible"
    exit 1
fi

echo "OK: NFS healthy"
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| Mount fails | Check `showmount -e <server>`, verify firewall |
| Stale handle | Force unmount: `umount -f <mount>` |
| Slow performance | Verify nconnect, check network throughput |
| Permission denied | Check export permissions, root_squash settings |

### Diagnostic Commands

```bash
# NFS statistics
nfsstat -c
nfsstat -m

# Check RPC services
rpcinfo -p <NFS_SERVER_IP>

# Test connectivity
showmount -e <NFS_SERVER_IP>

# System logs
journalctl -u nfs-client.target
dmesg | grep -i nfs
```

---

## Quick Reference

### Essential Commands

```bash
# Mount operations
mount -t nfs4 -o vers=4.1,nconnect=4 <server>:<export> <mount>
umount <mount>

# Status
mount | grep nfs
nfsstat -c
nfsstat -m

# Troubleshooting
showmount -e <server>
rpcinfo -p <server>
```

### Configuration Files

| File | Purpose |
|------|---------|
| `/etc/fstab` | Persistent mount configuration |
| `/etc/netplan/*.yaml` | Network configuration (Ubuntu) |
| `/etc/network/interfaces` | Network configuration (Debian) |
| `/etc/sysctl.d/99-nfs-tuning.conf` | Kernel tuning |

---

## Next Steps

- [NFS Quick Start](./QUICKSTART.md) - Get started quickly
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Block storage alternative
- [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md) - High-performance storage

