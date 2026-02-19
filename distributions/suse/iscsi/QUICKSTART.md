---
layout: default
title: iSCSI on SUSE/openSUSE - Quick Start Guide
---

# iSCSI on SUSE/openSUSE - Quick Start Guide

This guide provides a streamlined path to configure iSCSI storage on SUSE/openSUSE systems.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [iSCSI Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- SLES 15 SP3+ or openSUSE Leap 15.3+
- iSCSI storage array with portal IPs and target IQN
- Dedicated storage network interfaces
- Root or sudo access

{% include quickstart/glossary-link-iscsi.md %}

## Step 1: Install Packages

```bash
sudo zypper install -y open-iscsi multipath-tools
sudo systemctl enable --now iscsid multipathd
```

## Step 2: Configure Network Interfaces

{% include quickstart/network-suse.md %}

## Step 3: Configure Firewall

{% include quickstart/firewall-rhel.md %}

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 4: Configure iSCSI Initiator

```bash
# View/generate initiator name
cat /etc/iscsi/initiatorname.iscsi

# Set automatic startup
sudo sed -i 's/^node.startup = manual/node.startup = automatic/' /etc/iscsi/iscsid.conf
sudo systemctl restart iscsid
```

**Register this initiator IQN** with your storage array.

## Step 5: Create Interface Bindings

{% include quickstart/iscsi-interface-bindings.md %}

## Step 6: Discover and Login

{% include quickstart/iscsi-discover-login.md %}

## Step 7: Configure Multipath

{% include quickstart/iscsi-multipath-conf.md %}

## Step 8: Create LVM Storage

{% include quickstart/iscsi-lvm-storage.md %}

```bash
# Format and mount (SUSE: XFS recommended)
sudo mkfs.xfs /dev/iscsi-storage/data
sudo mkdir -p /mnt/iscsi-storage
sudo mount /dev/iscsi-storage/data /mnt/iscsi-storage

# Add to fstab
echo '/dev/iscsi-storage/data /mnt/iscsi-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 9: Verify

{% include quickstart/iscsi-verify.md %}

---

{% include quickstart/iscsi-quick-reference.md %}

---

## Next Steps

For production deployments, see [iSCSI Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Multipath configuration details
- Security best practices (AppArmor, CHAP, firewall options)
- Monitoring and troubleshooting
- High availability considerations

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

