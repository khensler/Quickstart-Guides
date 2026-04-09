---
layout: default
title: NFS Storage on HPE VM Essentials - Quick Start Guide
---

# NFS Storage on HPE VM Essentials - Quick Start Guide

This guide provides a streamlined path to configure NFS storage for HPE Virtual Machine Essentials (VME) clusters.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NFS Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- HPE VME cluster deployed and operational
- Ubuntu 22.04 or 24.04 on cluster hosts
- NFS server with exported share accessible from all cluster hosts
- Access to HPE VME Manager web interface
- Root or sudo access on cluster hosts

> **⚠️ Important - Ubuntu Installation:** During Ubuntu installation, configure ALL network interfaces you plan to use (management, storage, etc.) in the network setup step. Interfaces not configured during installation won't be visible in the HPE VM Console later and must be configured manually via netplan.

{% include quickstart/glossary-link-nfs.md %}

## Overview

HPE VME supports two storage layouts:
- **Converged (HCI)**: Uses Ceph for clustered storage (built-in)
- **Non-converged**: Uses external NFS or iSCSI storage

This guide covers configuring **NFS storage** for non-converged or mixed deployments.

## Step 1: Verify NFS Server Configuration

Ensure your NFS server exports are configured to allow all HPE VME hosts:

```bash
# On NFS server - example /etc/exports entry
/nfs/vme-datastore  10.100.1.0/24(rw,sync,no_subtree_check,no_root_squash)

# Apply changes
sudo exportfs -ra

# Verify exports
sudo exportfs -v
```

**Key NFS export options:**
- `rw` - Read/write access
- `sync` - Synchronous writes (recommended for VM storage)
- `no_root_squash` - Allow root access from clients
- `no_subtree_check` - Improves reliability

## Step 2: Verify Host Connectivity

On each HPE VME host, verify NFS connectivity:

```bash
# Install NFS client utilities (if not present)
sudo apt update && sudo apt install -y nfs-common

# Test NFS server accessibility
showmount -e <nfs_server_ip>

# Test mount manually
sudo mkdir -p /mnt/test-nfs
sudo mount -t nfs <nfs_server_ip>:/nfs/vme-datastore /mnt/test-nfs

# Verify access
ls -la /mnt/test-nfs
touch /mnt/test-nfs/test-file && rm /mnt/test-nfs/test-file

# Unmount test
sudo umount /mnt/test-nfs
```

Repeat on all cluster hosts.

## Step 3: Configure Network for NFS Traffic

For optimal performance, use dedicated storage interfaces.

### Option A: Using HPE VME Console (Recommended)

If you configured the storage interfaces during Ubuntu installation:

```bash
# Enter HPE VME Console
sudo hpe-vm

# Navigate to Network Configuration
# Configure storage interface with static IP and MTU 9000
```

### Option B: Using Netplan (Manual)

If interfaces weren't configured during installation or you prefer manual configuration:

```bash
# Edit netplan configuration
sudo vi /etc/netplan/01-storage.yaml
```

**Example 1: Single storage interface**
```yaml
network:
  version: 2
  ethernets:
    eth1:  # Storage interface
      addresses:
        - 10.100.1.101/24
      mtu: 9000
      routes: []
```

**Example 2: Bonded storage interfaces (recommended)**
```yaml
network:
  version: 2
  ethernets:
    eth1:
      dhcp4: false
    eth2:
      dhcp4: false
  bonds:
    bond1:
      interfaces: [eth1, eth2]
      addresses:
        - 10.100.1.101/24
      mtu: 9000
      parameters:
        mode: 802.3ad        # LACP - requires switch support
        lacp-rate: fast
        mii-monitor-interval: 100
        transmit-hash-policy: layer3+4
```

Apply configuration:

```bash
sudo netplan apply

# Verify
ip addr show bond1  # or eth1 for single interface
```

## Step 4: Add NFS Datastore in HPE VME Manager

1. Navigate to **Infrastructure > Clusters** in HPE VME Manager
2. Select your HPE VME cluster
3. Click the **Storage** tab
4. Select the **Data Stores** subtab
5. Click **ADD**
6. Configure the datastore:
   - **NAME**: Enter a descriptive name (e.g., `nfs-datastore-01`)
   - **TYPE**: Select `NFS Pool`
   - **SOURCE HOST**: Enter NFS server IP or hostname
   - **SOURCE DIRECTORY**: Enter the export path (e.g., `/nfs/vme-datastore`)
7. Click **SAVE**

> **⚠️ Note:** The datastore name cannot be changed after creation.

## Step 5: Wait for Initialization

The NFS datastore will take a few minutes to initialize. Monitor the status:

1. Stay on the **Storage > Data Stores** tab
2. Watch for the status to change to **Online**
3. Verify capacity and free space are displayed correctly

## Step 6: Use NFS Datastore for Virtual Machines

When provisioning new VMs:

1. Navigate to **Provisioning > Instances**
2. Click **+ ADD**
3. Select **HPE VM** Instance Type
4. On the **Configure** tab:
   - Select your cluster as **RESOURCE POOL**
   - Under **VOLUMES**, select the NFS datastore
   - Configure VM size and other options
5. Complete the wizard

For existing VMs, you can migrate storage to the NFS datastore.

## Step 7: Verify NFS Datastore Operation

```bash
# On any cluster host - verify NFS mount
df -h | grep nfs

# Check mounted NFS details
mount | grep nfs

# Verify I/O performance (basic test)
dd if=/dev/zero of=/path/to/nfs/test bs=1M count=100 oflag=direct
rm /path/to/nfs/test
```

---

## Quick Reference

### Common Commands

```bash
# Show NFS exports from server
showmount -e <nfs_server_ip>

# Check NFS mounts on host
mount | grep nfs

# NFS statistics
nfsstat -c

# Check NFS services
systemctl status nfs-common
```

### NFS Datastore Checklist

- [ ] NFS server exports configured for all hosts
- [ ] `no_root_squash` option set on exports
- [ ] All hosts can mount NFS share
- [ ] MTU 9000 configured end-to-end (recommended)
- [ ] Datastore added in HPE VME Manager
- [ ] Datastore shows Online status
- [ ] Test VM provisioned successfully

---

## Next Steps

For production deployments, see [NFS Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- NFS performance tuning
- Security best practices
- Monitoring and troubleshooting
- High availability considerations

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

