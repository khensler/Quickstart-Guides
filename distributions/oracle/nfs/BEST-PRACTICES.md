---
layout: default
title: NFS on Oracle Linux - Best Practices Guide
---

# NFS on Oracle Linux - Best Practices Guide

Comprehensive best practices for deploying NFS storage on Oracle Linux systems in production environments.

> **Related Guides:** For block storage alternatives, see:
> - [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md)
> - [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md)

---

{% include bestpractices/disclaimer-oracle.md %}

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Oracle Linux-Specific Considerations](#oracle-linux-specific-considerations)
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

- **Oracle Linux Hosts**: Multiple hosts with redundant network connectivity
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

## Oracle Linux-Specific Considerations

### Kernel Selection: UEK vs RHCK

Oracle Linux offers two kernel options:

| Kernel | Description | NFS nconnect |
|--------|-------------|--------------|
| **UEK 7** (OL9) | Unbreakable Enterprise Kernel | ✓ Supported |
| **UEK 6** (OL8) | Unbreakable Enterprise Kernel | ✓ Supported |
| **RHCK** | Red Hat Compatible Kernel | ✓ Supported |

**Recommendation**: Use UEK for better performance and latest features.

```bash
# Check current kernel
uname -r

# List available kernels
sudo dnf list installed kernel*

# Switch to UEK (if using RHCK)
sudo dnf install -y kernel-uek
sudo grubby --set-default /boot/vmlinuz-*uek*
```

### Package Installation

```bash
# Install NFS utilities
sudo dnf install -y nfs-utils rpcbind

# Enable services
sudo systemctl enable --now nfs-client.target rpcbind

# Verify installation
rpm -qa | grep nfs
```

### SELinux Configuration

SELinux is enabled by default on Oracle Linux:

```bash
# Allow NFS home directories
sudo setsebool -P use_nfs_home_dirs 1

# Allow httpd to use NFS (if applicable)
sudo setsebool -P httpd_use_nfs 1

# Check NFS-related booleans
getsebool -a | grep nfs
```

---

## Network Design

### Network Bonding

Configure bonded interfaces using nmcli:

```bash
# Create bond
sudo nmcli connection add type bond \
    con-name bond0 \
    ifname bond0 \
    bond.options "mode=802.3ad,miimon=100,xmit_hash_policy=layer3+4"

# Add slaves
sudo nmcli connection add type ethernet \
    slave-type bond \
    con-name bond0-slave1 \
    ifname eth1 \
    master bond0

sudo nmcli connection add type ethernet \
    slave-type bond \
    con-name bond0-slave2 \
    ifname eth2 \
    master bond0

# Configure IP and MTU
sudo nmcli connection modify bond0 \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.method manual \
    802-3-ethernet.mtu 9000

# Bring up the bond
sudo nmcli connection up bond0
```

### Understanding LACP Load Balancing

LACP uses hash-based distribution—there's no guarantee of balanced traffic:

- Each flow (source/dest IP+port) uses a single link
- Single NFS mount may use only one link
- Use `nconnect` to create multiple TCP connections that may hash to different links

### Firewall Configuration

```bash
# Allow NFS services
sudo firewall-cmd --permanent --add-service=nfs
sudo firewall-cmd --permanent --add-service=rpc-bind
sudo firewall-cmd --permanent --add-service=mountd
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-services
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
<NFS_SERVER_IP>:/data/oracle /mnt/pure-nfs nfs4 vers=4.1,nconnect=4,noatime,nodiratime,_netdev 0 0
```

### Persistent Mount via autofs

```bash
# Install autofs
sudo dnf install -y autofs

# Configure /etc/auto.master
echo '/mnt/nfs /etc/auto.nfs --timeout=300' | sudo tee -a /etc/auto.master

# Configure /etc/auto.nfs
echo 'pure-nfs -fstype=nfs4,vers=4.1,nconnect=4,noatime,nodiratime <NFS_SERVER_IP>:/data/oracle' | sudo tee /etc/auto.nfs

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

### Tuned Profile

```bash
# Use network-throughput profile
sudo tuned-adm profile network-throughput

# Verify
sudo tuned-adm active
```

### UEK-Specific Optimizations

UEK provides enhanced NFS performance. Ensure you're using the latest UEK:

```bash
# Update UEK
sudo dnf update kernel-uek

# Verify UEK is active
uname -r | grep uek
```

---

## Security Best Practices

### Network Isolation

- Use dedicated VLANs for NFS traffic
- Configure firewall rules to restrict access
- Never expose NFS to untrusted networks

### SELinux

Keep SELinux enabled and configure appropriate booleans:

```bash
# List NFS-related booleans
getsebool -a | grep nfs

# Set as needed
sudo setsebool -P use_nfs_home_dirs 1
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
```

### Ksplice for Zero-Downtime Updates

Oracle Linux supports Ksplice for kernel updates without reboots:

```bash
# Check Ksplice status
sudo ksplice status

# Apply updates
sudo ksplice -y upgrade
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
| Slow performance | Verify nconnect, check UEK version |
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

# Check kernel
uname -r
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
| `/etc/sysctl.d/99-nfs-tuning.conf` | Kernel tuning |
| `/etc/auto.master`, `/etc/auto.nfs` | Autofs configuration |

---

## Next Steps

- [NFS Quick Start](./QUICKSTART.md) - Get started quickly
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Block storage alternative
- [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md) - High-performance storage

