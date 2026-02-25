---
layout: default
title: NFS on XCP-ng - Quick Start Guide (Xen Orchestra)
---

# NFS on XCP-ng - Quick Start Guide

This guide walks you through configuring NFS storage on XCP-ng using **Xen Orchestra (XO)** web interface.

> **📘 For iSCSI storage:** See [iSCSI Quick Start](../iscsi/QUICKSTART.md) or [iSCSI GUI Guide](../iscsi/GUI-QUICKSTART.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.2 or later with Xen Orchestra installed
- NFS server with:
  - NFS export path configured
  - XCP-ng hosts allowed in export rules
  - NFSv3 or NFSv4.1 support
- Network connectivity between XCP-ng hosts and NFS server
- NFS server IP address and export path

> **📖 New to NFS storage?** See the [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

---

## Step 1: Prepare NFS Server

Ensure your NFS server has an export configured for XCP-ng.

### Example NFS Export Configuration

On your NFS server (e.g., `/etc/exports`):

```bash
/exports/xcpng-vms  10.100.1.0/24(rw,sync,no_subtree_check,no_root_squash)
```

> **Security Note:** `no_root_squash` is required for XCP-ng to manage VM files. Restrict access to your storage network.

### Pure Storage FlashArray NFS

If using Pure Storage FlashArray:

1. Navigate to **Storage → File Systems**
2. Create a new file system
3. Configure NFS export rules for your XCP-ng network
4. Note the NFS mount path

<!-- TODO: Add screenshot of Pure FlashArray NFS configuration -->
> **📸 Screenshot placeholder:** _Pure FlashArray NFS export configuration_

---

## Step 2: Verify Network Connectivity

Before adding NFS storage, verify connectivity from each XCP-ng host.

### Via SSH to Each Host

```bash
# Test connectivity to NFS server
ping -c 3 <NFS_SERVER_IP>

# Test NFS port (2049)
nc -zv <NFS_SERVER_IP> 2049

# List available exports
showmount -e <NFS_SERVER_IP>
```

Expected output from `showmount`:
```
Export list for 10.100.1.50:
/exports/xcpng-vms 10.100.1.0/24
```

<!-- TODO: Add screenshot of showmount output -->
> **📸 Screenshot placeholder:** _Terminal showing showmount -e output_

---

## Step 3: Add NFS Storage Repository

### Via Xen Orchestra

1. Click **New → Storage** in the top menu

<!-- TODO: Add screenshot of XO New Storage menu -->
> **📸 Screenshot placeholder:** _XO New Storage dropdown menu_

2. Select **NFS** as the storage type

<!-- TODO: Add screenshot of storage type selection -->
> **📸 Screenshot placeholder:** _Storage type selection showing NFS option_

3. Fill in the NFS connection details:

| Field | Value | Description |
|-------|-------|-------------|
| **Name** | `NFS-Storage-SR` | Descriptive name for the SR |
| **Description** | `NFS Storage Repository` | Optional description |
| **Host** | Select pool master | Initial host for connection |
| **Server** | `10.100.1.50` | NFS server IP address |
| **Path** | `/exports/xcpng-vms` | NFS export path |
| **NFS Version** | `3` or `4.1` | Match your server configuration |

<!-- TODO: Add screenshot of NFS connection form -->
> **📸 Screenshot placeholder:** _NFS SR creation form - connection details_

4. (Optional) Configure mount options:
   - Common options: `tcp,hard,intr,timeo=600,retrans=2`

<!-- TODO: Add screenshot showing mount options field -->
> **📸 Screenshot placeholder:** _NFS mount options configuration_

5. Click **Create**

<!-- TODO: Add screenshot of SR creation progress -->
> **📸 Screenshot placeholder:** _SR creation in progress_

6. Wait for the SR to be created and connected

<!-- TODO: Add screenshot of successful SR creation -->
> **📸 Screenshot placeholder:** _SR creation success message_

---

## Step 4: Verify Storage Repository

### Via Xen Orchestra

1. Navigate to **Home → SRs** (Storage Repositories)
2. Find your new NFS SR in the list
3. Click on it to view details

<!-- TODO: Add screenshot of SR list with NFS SR -->
> **📸 Screenshot placeholder:** _SR list showing new NFS SR_

4. Verify the SR shows:
   - **Status:** Connected (green)
   - **Type:** nfs
   - **Shared:** Yes (available on all hosts)

<!-- TODO: Add screenshot of NFS SR details -->
> **📸 Screenshot placeholder:** _NFS SR details page_

### Check PBD Connections

In the SR details, verify all hosts show connected PBDs:

<!-- TODO: Add screenshot of PBD status -->
> **📸 Screenshot placeholder:** _PBD connections showing all hosts connected to NFS SR_

---

## Step 5: Create a Test VM

### Via Xen Orchestra

1. Click **New → VM**
2. Select your template (e.g., Ubuntu, CentOS, Windows)
3. In the **Disks** section, select your new NFS SR

<!-- TODO: Add screenshot of VM creation with NFS SR -->
> **📸 Screenshot placeholder:** _VM creation showing NFS SR selected for disk storage_

4. Complete the VM creation wizard
5. Start the VM and verify it runs correctly

### Verify VM Disk Location

After creating the VM, verify the disk is stored on NFS:

1. Select the VM in XO
2. Go to the **Disks** tab
3. Verify the disk shows the NFS SR as its location

<!-- TODO: Add screenshot of VM disk details -->
> **📸 Screenshot placeholder:** _VM disk details showing NFS SR location_

---

## Step 6: Verify via CLI (Optional)

Connect to a host via SSH to verify the NFS mount:

```bash
# List SRs
xe sr-list type=nfs

# Check mount status
mount | grep nfs

# View SR directory
ls -la /var/run/sr-mount/<SR_UUID>/
```

---

## NFS vs iSCSI Comparison

| Feature | NFS | iSCSI |
|---------|-----|-------|
| **Protocol** | File-based | Block-based |
| **Setup Complexity** | Simpler | More complex |
| **Multipathing** | Built-in (TCP) | Requires dm-multipath |
| **Performance** | Good for mixed workloads | Better for I/O intensive |
| **Live Migration** | Supported | Supported |
| **Use Case** | General VM storage, ISO library | Database VMs, high IOPS |

---

## Troubleshooting

### SR Not Connecting

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
   - Verify XCP-ng host IPs are in the allowed list

<!-- TODO: Add screenshot of troubleshooting in XO logs -->
> **📸 Screenshot placeholder:** _XO Logs showing NFS connection errors_

### Mount Failures

1. **Check NFS version compatibility:**
   ```bash
   # Try mounting manually with specific version
   mount -t nfs -o vers=3 <NFS_SERVER_IP>:/path /mnt/test
   ```

2. **Check for stale mounts:**
   ```bash
   # On XCP-ng host
   mount | grep nfs
   ```

### Performance Issues

1. **Check NFS options:**
   - Use `tcp` instead of `udp`
   - Adjust `rsize` and `wsize` if needed

2. **Check network:**
   ```bash
   # Test throughput
   dd if=/dev/zero of=/var/run/sr-mount/<SR_UUID>/testfile bs=1M count=1024
   ```

---

## Quick Reference

| Task | Xen Orchestra Location |
|------|----------------------|
| View SRs | Home → SRs |
| Create VM | New → VM |
| Pool Settings | Home → Pools → Advanced |
| Logs | Home → Logs |

### CLI Commands

```bash
# List NFS SRs
xe sr-list type=nfs

# Get SR details
xe sr-param-list uuid=<SR_UUID>

# Check PBD status
xe pbd-list sr-uuid=<SR_UUID>

# Reconnect SR
xe pbd-plug uuid=<PBD_UUID>

# Check mounts
mount | grep nfs
```

---

## Next Steps

- [iSCSI Quick Start](../iscsi/QUICKSTART.md) - Block storage alternative
- [iSCSI GUI Guide](../iscsi/GUI-QUICKSTART.md) - iSCSI with Xen Orchestra
- [iSCSI Best Practices](../iscsi/BEST-PRACTICES.md) - Production deployment guidance
- [Common Troubleshooting]({{ site.baseurl }}/common/troubleshooting-common.html)

