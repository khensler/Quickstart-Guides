---
layout: default
title: NVMe-TCP on Proxmox VE - Quick Start Guide
---

# NVMe-TCP on Proxmox VE - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Proxmox VE.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Proxmox VE 8.x or later
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root access to all cluster nodes

{% include quickstart/glossary-link-nvme.md %}

{% include quickstart/arp-warning.md %}

## Step 1: Configure Network (All Nodes)

### Via GUI (Recommended)

Go to: **Datacenter → Node → System → Network**

1. Select storage interface → **Edit**
2. Set IP address and MTU 9000
3. Enable **Autostart**
4. Repeat for each interface
5. Click **Apply Configuration**

### Via CLI

Edit `/etc/network/interfaces`:

```bash
auto <INTERFACE_NAME_1>
iface <INTERFACE_NAME_1> inet static
    address <HOST_IP_1>/<CIDR>
    mtu 9000

auto <INTERFACE_NAME_2>
iface <INTERFACE_NAME_2> inet static
    address <HOST_IP_2>/<CIDR>
    mtu 9000
```

Apply: `ifreload -a`

## Step 2: Install Dependencies (All Nodes)

```bash
apt-get update && apt-get install -y nvme-cli

# Load modules
modprobe nvme nvme-tcp nvme-core

# Persist modules
cat > /etc/modules-load.d/nvme-tcp.conf << 'EOF'
nvme
nvme-tcp
nvme-core
EOF

# Enable native multipath
echo 'options nvme_core multipath=Y' > /etc/modprobe.d/nvme-tcp.conf
```

## Step 3: Generate Host NQN (All Nodes)

{% include quickstart/nvme-generate-hostnqn.md %}

**Register each node's host NQN** with your storage array.

## Step 4: Connect to NVMe Subsystems (All Nodes)

{% include quickstart/nvme-connect-storage.md %}

## Step 5: Configure IO Policy (All Nodes)

{% include quickstart/nvme-io-policy.md %}

## Step 6: Configure Persistent Connections (All Nodes)

{% include quickstart/nvme-persistent-connections.md %}

## Step 7: Create Storage in Proxmox

### Via GUI (One Node)

1. **Datacenter → Node → Disks** - Verify NVMe device visible
2. **LVM** → Create volume group
3. **Datacenter → Storage** → Edit → Enable **Shared**

### Via CLI (One Node)

```bash
pvcreate /dev/nvme0n1
vgcreate nvme-vg /dev/nvme0n1
pvesm add lvm nvme-datastore --vgname nvme-vg --content images,rootdir --shared 1
```

### Activate on Other Nodes

```bash
pvscan --cache
```

## Step 8: Verify

{% include quickstart/nvme-verify.md %}

```bash
# Check Proxmox storage
pvesm status
```

---

{% include quickstart/nvme-quick-reference.md %}

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (firewall options)
- Monitoring and troubleshooting
- High availability considerations
- Proxmox clustering considerations

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)
