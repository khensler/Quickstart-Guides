---
layout: default
title: Fibre Channel on SUSE/openSUSE - Quick Start Guide
---

# Fibre Channel on SUSE/openSUSE - Quick Start Guide

This guide provides a streamlined path to configure Fibre Channel storage on SUSE-based systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [FC Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- SUSE Linux Enterprise Server (SLES) 15 SP4+ or openSUSE Leap 15.4+
- Fibre Channel HBA installed and cabled to the FC fabric
- Fabric zoning and volume presentation configured by your SAN administrator
- Root or sudo access

{% include quickstart/glossary-link-fc.md %}

## Step 1: Install Packages

```bash
sudo zypper install -y multipath-tools sg3_utils sysfsutils
sudo systemctl enable --now multipathd
```

## Step 2: Verify HBA and Discover WWPNs

{% include quickstart/fc-hba-verify.md %}

## Step 3: Register WWPNs and Present Volume

{% include quickstart/fc-zoning-checklist.md %}

## Step 4: Rescan for Presented LUNs

{% include quickstart/fc-rescan-luns.md %}

## Step 5: Configure Multipath

{% include quickstart/fc-multipath-conf.md %}

> **Alternative:** For detailed multipath options, see [Best Practices - Multipath Configuration](./BEST-PRACTICES.md#multipath-configuration).

## Step 6: Create LVM Storage

{% include quickstart/fc-lvm-storage.md %}

```bash
# Format and mount (SUSE: XFS recommended for production)
sudo mkfs.xfs /dev/fc-storage/data
sudo mkdir -p /mnt/fc-storage
sudo mount /dev/fc-storage/data /mnt/fc-storage

# Add to fstab
echo '/dev/fc-storage/data /mnt/fc-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 7: Verify

{% include quickstart/fc-verify.md %}

---

{% include quickstart/fc-quick-reference.md %}

---

## Next Steps

For production deployments, see [FC Best Practices](./BEST-PRACTICES.md) for:
- FC architecture and fabric redundancy
- HBA driver tuning (queue depth, devloss timers)
- Multipath configuration details
- YaST storage management notes
- Monitoring and troubleshooting

**Additional Resources:**
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)
