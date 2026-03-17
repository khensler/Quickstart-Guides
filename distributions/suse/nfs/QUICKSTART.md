---
layout: default
title: NFS on SUSE/openSUSE - Quick Start Guide
---

# NFS on SUSE/openSUSE - Quick Start Guide

This guide provides a streamlined path to configure NFS storage on SUSE Linux Enterprise and openSUSE systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NFS Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- SUSE Linux Enterprise Server 15 SP3+ or openSUSE Leap 15.3+
- Everpure FlashArray with:
  - NFS file interface configured
  - NFS export policy created with NFSv4.1 enabled (recommended)
  - Export path created (e.g., `/data/suse`)
  - No root squash enabled for client IPs
- Dedicated storage network interfaces (recommended)
- Root or sudo access

---

## Step 1: Install NFS Client

```bash
# Install NFS utilities
sudo zypper install -y nfs-client

# Enable and start required services
sudo systemctl enable --now nfs-client.target
sudo systemctl enable --now rpcbind
```

---

## Step 2: Verify Network Connectivity

{% include quickstart/nfs-verify-connectivity.md %}

---

## Step 3: Configure Firewall

```bash
# Using firewalld
sudo firewall-cmd --permanent --add-service=nfs
sudo firewall-cmd --permanent --add-service=rpc-bind
sudo firewall-cmd --reload

# Or using YaST
sudo yast firewall
```

---

## Step 4: Create Mount Point and Mount NFS

```bash
# Create mount point
sudo mkdir -p /mnt/pure-nfs

# Mount with recommended options
sudo mount -t nfs4 -o vers=4.1,nconnect=4,noatime,nodiratime \
    <NFS_SERVER_IP>:/data/suse /mnt/pure-nfs

# Verify mount
mount | grep nfs
df -h /mnt/pure-nfs
```

---

## Step 5: Configure Persistent Mount

Add to `/etc/fstab` for automatic mounting at boot:

```bash
# Add fstab entry
echo '<NFS_SERVER_IP>:/data/suse /mnt/pure-nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime,_netdev 0 0' | sudo tee -a /etc/fstab

# Test fstab entry
sudo umount /mnt/pure-nfs
sudo mount -a

# Verify
mount | grep nfs
```

{% include quickstart/nfs-mount-options.md %}

---

## Step 6: Verify NFS Mount

{% include quickstart/nfs-verify-mount.md %}

---

## Quick Reference

{% include quickstart/nfs-quick-reference.md %}

---

## Troubleshooting

{% include quickstart/nfs-troubleshooting.md %}

**SUSE-specific:**
```bash
# Check AppArmor (if enabled)
sudo aa-status
```

---

## Next Steps

For production deployments, see [NFS Best Practices](./BEST-PRACTICES.md) for:
- Network bonding with wicked
- Performance tuning with nconnect
- YaST configuration options
- Monitoring and troubleshooting

**Related Guides:**
- [iSCSI Quick Start](../iscsi/QUICKSTART.md) - Block storage alternative
- [NVMe-TCP Quick Start](../nvme-tcp/QUICKSTART.md) - High-performance block storage

