---
layout: default
title: NVMe-TCP on Oracle Linux - Quick Start Guide
---

# NVMe-TCP on Oracle Linux - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Oracle Linux.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Oracle Linux 8.x or 9.x with UEK R7 (5.15+) recommended
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

{% include quickstart/glossary-link-nvme.md %}

{% include quickstart/arp-warning.md %}

## Step 1: Install Packages

```bash
sudo dnf install -y nvme-cli
sudo modprobe nvme-tcp
echo "nvme-tcp" | sudo tee /etc/modules-load.d/nvme-tcp.conf
```

## Step 2: Configure Network Interfaces

{% include quickstart/network-rhel.md %}

## Step 3: Configure Firewall

{% include quickstart/firewall-rhel.md %}

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 4: Generate Host NQN

{% include quickstart/nvme-generate-hostnqn.md %}

## Step 5: Connect to NVMe Subsystems

{% include quickstart/nvme-connect-storage.md %}

## Step 6: Configure IO Policy

{% include quickstart/nvme-io-policy.md %}

## Step 7: Configure Persistent Connections

{% include quickstart/nvme-persistent-connections.md %}

## Step 8: Create LVM Storage

{% include quickstart/nvme-lvm-storage.md %}

```bash
# Format and mount (Oracle Linux: XFS recommended)
sudo mkfs.xfs /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 9: Verify

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
- UEK vs RHCK kernel selection
- Ksplice zero-downtime updates

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

