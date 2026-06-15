---
layout: default
title: Fibre Channel on Proxmox VE - Quick Start Guide
---

# Fibre Channel on Proxmox VE - Quick Start Guide

This guide provides a streamlined path to configure Fibre Channel storage on Proxmox VE.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [FC Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Proxmox VE 8.x or later
- Fibre Channel HBA installed in each cluster node and cabled to the FC fabric
- Fabric zoning and volume presentation configured by your SAN administrator
- Root access to all cluster nodes

{% include quickstart/glossary-link-fc.md %}

## Step 1: Install Packages

Run on **every cluster node**:

```bash
apt update
apt install -y multipath-tools sg3-utils sysfsutils
systemctl enable --now multipathd
```

## Step 2: Verify HBA and Discover WWPNs

Run on **every cluster node**:

{% include quickstart/fc-hba-verify.md %}

> **Collect WWPNs from all cluster nodes** before proceeding to Step 3 — every node that will access the volume must be registered on the array.

## Step 3: Register WWPNs and Present Volume

{% include quickstart/fc-zoning-checklist.md %}

## Step 4: Rescan for Presented LUNs

Run on **every cluster node**:

{% include quickstart/fc-rescan-luns.md %}

## Step 5: Configure Multipath

Run on **every cluster node**:

{% include quickstart/fc-multipath-conf.md %}

> **Note:** For comprehensive multipath concepts and configuration patterns, see [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html).

## Step 6: Create LVM

Run on **one node** — the volume group will be shared across the cluster:

{% include quickstart/fc-lvm-storage.md %}

The example output from `multipath -ll` shows the WWID of the device. Use the WWID-based device path for LVM to ensure consistent naming across all cluster nodes:

```bash
# Example output showing WWID-based device path:
# mpatha (3624a937...) dm-0 PURE,FlashArray

# Create PV and VG using the WWID-based path
pvcreate /dev/mapper/3624a937...
vgcreate vg_fc /dev/mapper/3624a937...

# Verify
vgs
pvs
```

## Step 7: Add LVM Storage to Proxmox

### CLI

```bash
# Add shared LVM storage to Proxmox
pvesm add lvm fc-datastore \
    --vgname vg_fc \
    --content images,rootdir \
    --shared 1

# Verify
pvesm status
```

### GUI

Go to: **Datacenter → Storage**. Click **Add → LVM**.

Name the storage in the ID field. Select the volume group in the **Volume Group** dropdown. Check the **Shared** box. Select the appropriate Content types. Enable the volume on other nodes by clearing the Nodes field. Click **Add**.

## Step 8: Verify

Run on **every cluster node**:

{% include quickstart/fc-verify.md %}

In the Proxmox UI, navigate to **Datacenter → Storage** and confirm the datastore status shows **Active** on all nodes.

---

{% include quickstart/fc-quick-reference.md %}

---

## Next Steps

For production deployments, see [FC Best Practices](./BEST-PRACTICES.md) for:
- Cluster HA and FC storage considerations
- HBA driver tuning
- Multipath configuration details
- Monitoring and troubleshooting

**Additional Resources:**
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)
