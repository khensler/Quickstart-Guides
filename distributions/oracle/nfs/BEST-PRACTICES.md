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

{% include nfs-vip-failover.md %}

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

{% include nfs-lacp-load-balancing.md %}

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

{% include nfs-mount-options-table.md %}

### Persistent Mount via fstab

```bash
# Add to /etc/fstab
<NFS_SERVER_IP>:/data/oracle /mnt/pure-nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime,_netdev 0 0
```

### Persistent Mount via autofs

```bash
# Install autofs
sudo dnf install -y autofs

# Configure /etc/auto.master
echo '/mnt/nfs /etc/auto.nfs --timeout=300' | sudo tee -a /etc/auto.master

# Configure /etc/auto.nfs
echo 'pure-nfs -fstype=nfs4,vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime <NFS_SERVER_IP>:/data/oracle' | sudo tee /etc/auto.nfs

# Enable autofs
sudo systemctl enable --now autofs
```

---

## Performance Optimization

{% include nfs-nconnect.md %}

{% include nfs-kernel-tuning.md %}

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

{% include nfs-troubleshooting-common.md %}

**Oracle Linux-specific:**
```bash
# Check SELinux
getenforce
sudo setsebool -P use_nfs_home_dirs 1

# Check kernel (UEK recommended)
uname -r
```

---

{% include bestpractices/nfs-quick-reference.md %}

---

## Next Steps

- [NFS Quick Start](./QUICKSTART.md) - Get started quickly
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Block storage alternative
- [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md) - High-performance storage

