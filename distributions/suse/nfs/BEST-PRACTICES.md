---
layout: default
title: NFS on SUSE/openSUSE - Best Practices Guide
---

# NFS on SUSE/openSUSE - Best Practices Guide

Comprehensive best practices for deploying NFS storage on SUSE Linux Enterprise and openSUSE systems in production environments.

> **Related Guides:** For block storage alternatives, see:
> - [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md)
> - [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md)

---

{% include bestpractices/disclaimer-suse.md %}

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [SUSE-Specific Considerations](#suse-specific-considerations)
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

- **SUSE Hosts**: Multiple hosts with redundant network connectivity
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

## SUSE-Specific Considerations

### Supported Versions

| Distribution | Kernel | NFS Support |
|--------------|--------|-------------|
| SLES 15 SP5 | 5.14+ | NFSv4.1, nconnect supported |
| SLES 15 SP4 | 5.14+ | NFSv4.1, nconnect supported |
| SLES 15 SP3 | 5.3+ | NFSv4.1, nconnect supported |
| openSUSE Leap 15.5 | 5.14+ | NFSv4.1, nconnect supported |
| openSUSE Leap 15.4 | 5.14+ | NFSv4.1, nconnect supported |

### Package Installation

```bash
# Install NFS client
sudo zypper install -y nfs-client nfs-utils

# Enable services
sudo systemctl enable --now nfs-client.target rpcbind

# Verify installation
rpm -qa | grep nfs
```

### YaST Configuration

SUSE provides YaST for graphical configuration:

```bash
# Launch YaST NFS client module
sudo yast nfs-client

# Or use ncurses interface
sudo yast2 nfs-client
```

---

## Network Design

### Network Bonding with Wicked

SUSE uses wicked for network management:

```bash
# Create bond configuration
cat > /etc/sysconfig/network/ifcfg-bond0 << 'EOF'
STARTMODE=auto
BOOTPROTO=static
IPADDR=10.100.1.101/24
BONDING_MASTER=yes
BONDING_SLAVE_0=eth1
BONDING_SLAVE_1=eth2
BONDING_MODULE_OPTS="mode=802.3ad miimon=100 xmit_hash_policy=layer3+4"
MTU=9000
EOF

# Configure slaves
for iface in eth1 eth2; do
cat > /etc/sysconfig/network/ifcfg-$iface << EOF
STARTMODE=hotplug
BOOTPROTO=none
MTU=9000
EOF
done

# Restart network
sudo systemctl restart wicked
```

### Understanding LACP Load Balancing

LACP uses hash-based distribution—there's no guarantee of balanced traffic:

- Each flow (source/dest IP+port) uses a single link
- Single NFS mount may use only one link
- Use `nconnect` to create multiple TCP connections that may hash to different links

### Firewall Configuration

```bash
# Using firewalld
sudo firewall-cmd --permanent --add-service=nfs
sudo firewall-cmd --permanent --add-service=rpc-bind
sudo firewall-cmd --permanent --add-service=mountd
sudo firewall-cmd --reload

# Or using YaST
sudo yast firewall
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
<NFS_SERVER_IP>:/data/suse /mnt/pure-nfs nfs4 vers=4.1,nconnect=4,noatime,nodiratime,_netdev 0 0
```

### Persistent Mount via autofs

```bash
# Install autofs
sudo zypper install -y autofs

# Configure /etc/auto.master
echo '/mnt/nfs /etc/auto.nfs --timeout=300' | sudo tee -a /etc/auto.master

# Configure /etc/auto.nfs
echo 'pure-nfs -fstype=nfs4,vers=4.1,nconnect=4,noatime,nodiratime <NFS_SERVER_IP>:/data/suse' | sudo tee /etc/auto.nfs

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
- Configure firewall rules to restrict access
- Never expose NFS to untrusted networks

### AppArmor Configuration

AppArmor is available on SUSE. Check status:

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
| `/etc/sysconfig/network/ifcfg-*` | Network configuration (wicked) |
| `/etc/sysctl.d/99-nfs-tuning.conf` | Kernel tuning |
| `/etc/auto.master`, `/etc/auto.nfs` | Autofs configuration |

---

## Next Steps

- [NFS Quick Start](./QUICKSTART.md) - Get started quickly
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Block storage alternative
- [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md) - High-performance storage

