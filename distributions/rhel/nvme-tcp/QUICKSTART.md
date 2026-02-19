---
layout: default
title: NVMe-TCP on RHEL/Rocky/AlmaLinux - Quick Start Guide
---

# NVMe-TCP on RHEL/Rocky/AlmaLinux - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on RHEL-based systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- RHEL 8.x/9.x, Rocky Linux 8/9, AlmaLinux 8/9
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

{% include quickstart/glossary-link-nvme.md %}

## Step 1: Install NVMe Tools

```bash
sudo dnf install -y nvme-cli
nvme version
```

{% include quickstart/nvme-enable-multipath.md %}

## Step 3: Configure Network Interfaces

Configure dedicated storage interfaces with jumbo frames and no default route:

{% include quickstart/network-rhel.md %}

{% include quickstart/arp-warning.md %}

## Step 4: Configure Firewall

{% include quickstart/firewall-rhel.md %}

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 5: Generate Host NQN

{% include quickstart/nvme-generate-hostnqn.md %}

## Step 6: Connect to Storage

{% include quickstart/nvme-connect-storage.md %}

## Step 7: Configure IO Policy

{% include quickstart/nvme-io-policy.md %}

## Step 8: Configure Persistent Connections

{% include quickstart/nvme-persistent-connections.md %}

## Step 9: Create LVM Storage

{% include quickstart/nvme-lvm-storage.md %}

```bash
# Format and mount (RHEL: XFS recommended)
sudo mkfs.xfs /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 10: Verify

{% include quickstart/nvme-verify.md %}

---

{% include quickstart/nvme-quick-reference.md %}

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (SELinux, firewall options)
- Monitoring and troubleshooting
- High availability considerations

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

