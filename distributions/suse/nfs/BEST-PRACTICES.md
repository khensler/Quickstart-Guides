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

{% include nfs-vip-failover.md %}

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

{% include nfs-lacp-load-balancing.md %}

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

{% include nfs-mount-options-table.md %}

### Persistent Mount via fstab

```bash
# Add to /etc/fstab
<NFS_SERVER_IP>:/data/suse /mnt/pure-nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime,_netdev 0 0
```

### Persistent Mount via autofs

```bash
# Install autofs
sudo zypper install -y autofs

# Configure /etc/auto.master
echo '/mnt/nfs /etc/auto.nfs --timeout=300' | sudo tee -a /etc/auto.master

# Configure /etc/auto.nfs
echo 'pure-nfs -fstype=nfs4,vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime <NFS_SERVER_IP>:/data/suse' | sudo tee /etc/auto.nfs

# Enable autofs
sudo systemctl enable --now autofs
```

---

## Performance Optimization

{% include nfs-nconnect.md %}

{% include nfs-kernel-tuning.md %}

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

{% include nfs-troubleshooting-common.md %}

**SUSE-specific:**
```bash
# System logs
journalctl -u nfs-client.target
dmesg | grep -i nfs

# Check AppArmor
sudo aa-status
```

---

{% include bestpractices/nfs-quick-reference.md %}

**Additional SUSE files:**

| File | Purpose |
|------|---------|
| `/etc/sysconfig/network/ifcfg-*` | Network configuration (wicked) |

---

## Next Steps

- [NFS Quick Start](./QUICKSTART.md) - Get started quickly
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Block storage alternative
- [NVMe-TCP Best Practices](../nvme-tcp/BEST-PRACTICES.md) - High-performance storage

