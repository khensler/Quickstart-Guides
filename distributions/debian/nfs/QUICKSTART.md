---
layout: default
title: NFS on Debian/Ubuntu - Quick Start Guide
---

# NFS on Debian/Ubuntu - Quick Start Guide

This guide provides a streamlined path to configure NFS storage on Debian/Ubuntu systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NFS Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Debian 11+ or Ubuntu 20.04 LTS+
- Everpure FlashArray with:
  - NFS file interface configured
  - NFS export policy created with NFSv4.1 enabled (recommended)
  - Export path created (e.g., `/data/debian`)
  - No root squash enabled for client IPs
- Dedicated storage network interfaces (recommended)
- Root or sudo access

---

## Step 1: Install NFS Client

```bash
# Update package lists
sudo apt update

# Install NFS utilities
sudo apt install -y nfs-common

# Verify installation
dpkg -l | grep nfs-common
```

---

## Step 2: Verify Network Connectivity

```bash
# Test connectivity to NFS server
ping -c 3 <NFS_SERVER_IP>

# Test NFS port (2049)
nc -zv <NFS_SERVER_IP> 2049

# List available exports
showmount -e <NFS_SERVER_IP>
```

---

## Step 3: Configure Firewall (if enabled)

```bash
# UFW (Ubuntu default)
sudo ufw allow out to any port 2049
sudo ufw allow out to any port 111

# Verify
sudo ufw status
```

---

## Step 4: Create Mount Point and Mount NFS

```bash
# Create mount point
sudo mkdir -p /mnt/pure-nfs

# Mount with recommended options
sudo mount -t nfs4 -o vers=4.1,nconnect=4,noatime,nodiratime \
    <NFS_SERVER_IP>:/data/debian /mnt/pure-nfs

# Verify mount
mount | grep nfs
df -h /mnt/pure-nfs
```

---

## Step 5: Configure Persistent Mount

Add to `/etc/fstab` for automatic mounting at boot:

```bash
# Add fstab entry
echo '<NFS_SERVER_IP>:/data/debian /mnt/pure-nfs nfs4 vers=4.1,nconnect=4,noatime,nodiratime,_netdev 0 0' | sudo tee -a /etc/fstab

# Test fstab entry
sudo umount /mnt/pure-nfs
sudo mount -a

# Verify
mount | grep nfs
```

> **📘 Recommended Options:**
> - `vers=4.1` — NFSv4.1 for improved locking and session recovery
> - `nconnect=4` — Multiple TCP connections for improved throughput (values 4-8 recommended)
> - `noatime,nodiratime` — Don't update access times, reducing metadata I/O
> - `_netdev` — Wait for network before mounting

---

## Step 6: Verify NFS Mount

```bash
# Check mount options
mount | grep nfs

# Verify nconnect is active
cat /proc/fs/nfsfs/servers

# Test read/write
echo "NFS test" | sudo tee /mnt/pure-nfs/test.txt
cat /mnt/pure-nfs/test.txt
sudo rm /mnt/pure-nfs/test.txt
```

---

## Quick Reference

| Task | Command |
|------|---------|
| List NFS mounts | `mount \| grep nfs` |
| Show exports | `showmount -e <server>` |
| Mount NFS | `mount -t nfs4 <server>:<export> <mountpoint>` |
| Unmount NFS | `umount <mountpoint>` |
| NFS statistics | `nfsstat -c` |
| Mount info | `nfsstat -m` |

---

## Troubleshooting

### Mount Fails

```bash
# Check network connectivity
ping <NFS_SERVER_IP>
nc -zv <NFS_SERVER_IP> 2049

# Check exports
showmount -e <NFS_SERVER_IP>

# Check AppArmor (if enabled)
sudo aa-status
```

### Performance Issues

```bash
# Check NFS version and options
nfsstat -m

# Verify nconnect
cat /proc/fs/nfsfs/servers
```

---

## Next Steps

For production deployments, see [NFS Best Practices](./BEST-PRACTICES.md) for:
- Network bonding and redundancy
- Performance tuning with nconnect
- AppArmor configuration
- Monitoring and troubleshooting

**Related Guides:**
- [iSCSI Quick Start](../iscsi/QUICKSTART.md) - Block storage alternative
- [NVMe-TCP Quick Start](../nvme-tcp/QUICKSTART.md) - High-performance block storage

