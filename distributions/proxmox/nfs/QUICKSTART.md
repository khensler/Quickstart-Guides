---
layout: default
title: NFS on Proxmox VE - Quick Start Guide
---

# NFS on Proxmox VE - Quick Start Guide

This guide provides a streamlined path to configure NFS storage on Proxmox VE.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NFS Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Proxmox VE 8.x or later
- Everpure FlashArray with:
  - NFS file interface configured
  - NFS export policy created with NFSv4.1 enabled (recommended)
  - Export path created (e.g., `/proxmox/VMs`)
  - No root squash enabled for Proxmox host IPs
- Dedicated storage network interfaces (recommended)
- Network connectivity between Proxmox hosts and FlashArray NFS interface

---

## Step 1: Verify Network Connectivity

Before adding NFS storage, verify connectivity from each Proxmox node.

{% include quickstart/nfs-verify-connectivity.md %}

Expected output from `showmount`:
```
Export list for 10.10.3.15:
/proxmox/VMs 10.10.3.0/24
```

---

## Step 2: Install NFS Client (if needed)

NFS client utilities are typically pre-installed on Proxmox VE. Verify or install:

```bash
# Check if NFS utilities are installed
dpkg -l | grep nfs-common

# Install if needed
apt update
apt install -y nfs-common

# Verify NFS version support
cat /proc/fs/nfsd/versions
```

---

## Step 3: Add NFS Storage to Proxmox

### Option A: Via GUI

1. Navigate to **Datacenter → Storage → Add → NFS**

2. Fill in the storage details:

| Field | Value | Description |
|-------|-------|-------------|
| **ID** | `pure-nfs` | Unique storage identifier |
| **Server** | `10.10.3.15` | FlashArray NFS file interface IP |
| **Export** | `/proxmox/VMs` | NFS export path |
| **Content** | `Disk image, Container` | Select based on your needs |
| **Nodes** | All or specific | Leave empty for all nodes |
| **Enable** | ✓ | Enable the storage |

3. Under **NFS Options**:

| Field | Value | Description |
|-------|-------|-------------|
| **NFS Version** | `4.1` | NFSv4.1 recommended for Pure |

4. Click **Add**

5. **Set recommended mount options via CLI** (the GUI does not expose these options):

```bash
# Add recommended NFS options (includes failover-optimized settings)
pvesm set pure-nfs --options "vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime"
```

> **⚠️ Note:** After setting mount options, you may need to disable and re-enable the storage (or remount on each node) for changes to take effect.

### Option B: Via CLI

```bash
# Add NFS storage with all recommended options
pvesm add nfs pure-nfs \
    --server <NFS_SERVER_IP> \
    --export /proxmox/VMs \
    --content images,rootdir,vztmpl,iso \
    --options vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime

# Verify storage was added
pvesm status
```

{% include quickstart/nfs-mount-options.md %}

---

## Step 4: Verify NFS Mount

```bash
# Check mount status on all nodes
mount | grep nfs

# Example output with nconnect:
# 10.10.3.15:/proxmox/VMs on /mnt/pve/pure-nfs type nfs4 (rw,vers=4.1,nconnect=4,...)

# Verify nconnect is active
cat /proc/fs/nfsfs/servers

# List storage directory
ls -la /mnt/pve/pure-nfs/

# Check storage status
pvesm status
```

---

## Quick Reference

| Task | Command / Location |
|------|-------------------|
| List NFS storage | `pvesm status` |
| Check mounts | `mount \| grep nfs` |
| Add NFS storage | Datacenter → Storage → Add → NFS |
| View storage content | `/mnt/pve/<storage-id>/` |
| Storage logs | `journalctl -u pvestatd` |

### CLI Commands

```bash
# List all storage
pvesm status

# Get storage details
pvesm list pure-nfs

# Enable storage on node
pvesm set pure-nfs --nodes pve1,pve2,pve3

# Disable storage
pvesm set pure-nfs --disable 1
```

---

## Troubleshooting

### NFS Mount Fails

1. **Check network connectivity:**
   ```bash
   ping <NFS_SERVER_IP>
   nc -zv <NFS_SERVER_IP> 2049
   ```

2. **Check NFS exports:**
   ```bash
   showmount -e <NFS_SERVER_IP>
   ```

3. **Check firewall on NFS server:**
   - Ensure ports 111 (rpcbind) and 2049 (NFS) are open

4. **Check export permissions:**
   - Verify Proxmox host IPs are in the allowed list
   - Ensure no_root_squash is enabled

### Performance Issues

1. **Check NFS version:**
   ```bash
   nfsstat -m
   ```
   Ensure NFSv4.1 is being used.

2. **Test throughput:**
   ```bash
   dd if=/dev/zero of=/mnt/pve/pure-nfs/testfile bs=1M count=1024 oflag=direct
   rm /mnt/pve/pure-nfs/testfile
   ```

---

## Next Steps

For production deployments, see [NFS Best Practices](./BEST-PRACTICES.md) for:
- Network design and optimization
- High availability configuration
- Performance tuning
- Security best practices
- Monitoring and troubleshooting

**Related Guides:**
- [iSCSI Quick Start](../iscsi/QUICKSTART.md) - Block storage alternative
- [NVMe-TCP Quick Start](../nvme-tcp/QUICKSTART.md) - High-performance block storage

