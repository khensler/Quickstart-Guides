---
layout: default
title: NVMe-TCP on XCP-ng - Quick Start Guide
---

# NVMe-TCP on XCP-ng - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on XCP-ng.

> **⚠️ Experimental:** NVMe-TCP is not officially documented by XCP-ng. This guide is based on standard Linux NVMe-TCP configuration and may require additional testing in your environment.

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.2 or later
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root access to all pool hosts

{% include quickstart/glossary-link-nvme.md %}

{% include quickstart/arp-warning.md %}

## Step 1: Configure Storage Network Interfaces

Configure dedicated network interfaces for NVMe-TCP traffic. Replace values as appropriate for your environment.

```bash
# List available PIFs
xe pif-list

# Configure static IP on storage interface
xe pif-reconfigure-ip uuid=<PIF_UUID> mode=static IP=<HOST_IP> netmask=<NETMASK>

# Verify MTU settings (optional: set to 9000 for jumbo frames)
xe pif-param-set uuid=<PIF_UUID> other-config:mtu=9000

# Verify interface configuration
xe pif-list params=uuid,device,IP,netmask
```

## Step 2: Install NVMe CLI Tools

Install the required NVMe CLI tools on each XCP-ng host:

```bash
# Install nvme-cli
yum install -y nvme-cli

# Load required kernel modules
modprobe nvme nvme-tcp nvme-core

# Persist modules across reboots
cat > /etc/modules-load.d/nvme-tcp.conf << 'EOF'
nvme
nvme-tcp
nvme-core
EOF

# Enable native NVMe multipath
echo 'options nvme_core multipath=Y' > /etc/modprobe.d/nvme-tcp.conf
```

## Step 3: Generate Host NQN (All Hosts)

{% include quickstart/nvme-generate-hostnqn.md %}

**Register each host's NQN** with your storage array's allowed hosts list.

## Step 4: Connect to NVMe Subsystems (All Hosts)

{% include quickstart/nvme-connect-storage.md %}

## Step 5: Configure IO Policy (All Hosts)

{% include quickstart/nvme-io-policy.md %}

## Step 6: Configure Persistent Connections (All Hosts)

{% include quickstart/nvme-persistent-connections.md %}

## Step 7: Create Storage Repository

Since NVMe-TCP storage appears as a local block device, create an LVM-based SR:

```bash
# Identify the NVMe device
nvme list

# Create LVM SR using the NVMe device
xe sr-create name-label="NVMe-TCP Storage" type=lvm shared=true \
    device-config:device=/dev/nvme0n1

# Verify SR creation
xe sr-list type=lvm name-label="NVMe-TCP Storage"
```

> **Note:** For shared storage across pool hosts, ensure all hosts have NVMe connections established before creating the SR.

### Activate on Other Hosts

After creating the SR on one host, activate it on other pool hosts:

```bash
# Scan for new physical volumes
pvscan --cache

# Verify SR is available
xe sr-list
```

## Step 8: Verify Configuration

{% include quickstart/nvme-verify.md %}

```bash
# Check XCP-ng storage status
xe sr-list
xe pbd-list sr-uuid=<SR_UUID>
```

---

{% include quickstart/nvme-quick-reference.md %}

---

## Next Steps

For production deployments, consult the official documentation:
- [XCP-ng Storage Documentation](https://docs.xcp-ng.org/storage/)
- [XCP-ng Networking](https://docs.xcp-ng.org/networking/)

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

