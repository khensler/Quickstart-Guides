---
layout: default
title: NVMe-TCP on Proxmox VE - Quick Start Guide
---

# NVMe-TCP on Proxmox VE - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Proxmox VE.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:** This guide is **specific to Pure Storage** and for reference only. Always consult official Proxmox VE and storage vendor documentation. Test thoroughly in a lab environment before production use.

---

## Prerequisites

- Proxmox VE 8.x or later
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root access to all cluster nodes

> **📖 New to NVMe-TCP?** See the [Storage Terminology Glossary]({% link _includes/glossary.md %})

> **⚠️ Same-Subnet Multipath:** If using multiple interfaces on the same subnet, configure ARP settings. See [ARP Configuration]({% link _includes/network-concepts.md %}).

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

```bash
mkdir -p /etc/nvme
[ ! -f /etc/nvme/hostnqn ] && nvme gen-hostnqn > /etc/nvme/hostnqn
cat /etc/nvme/hostnqn
```

**Register each node's host NQN** with your storage array.

## Step 4: Connect to NVMe Subsystems (All Nodes)

```bash
# Connect via first interface
nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Connect via second interface
nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Verify
nvme list-subsys
```

## Step 5: Configure IO Policy (All Nodes)

```bash
# Create udev rule for persistence
cat > /etc/udev/rules.d/99-nvme-iopolicy.rules << 'EOF'
ACTION=="add", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF

udevadm control --reload-rules && udevadm trigger

# Apply to existing subsystems
for s in /sys/class/nvme-subsystem/nvme-subsys*/iopolicy; do
    echo "queue-depth" > "$s" 2>/dev/null || true
done
```

## Step 6: Configure Persistent Connections (All Nodes)

```bash
# Create discovery configuration
cat > /etc/nvme/discovery.conf << 'EOF'
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1>
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1>
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2>
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2>
EOF

systemctl enable nvmf-autoconnect.service
```

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

```bash
# Check connections
nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check Proxmox storage
pvesm status
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `nvme discover -t tcp -a <IP> -s 8009` | Discover subsystems (port 8009) |
| `nvme connect -t tcp -a <IP> -s 4420 -n <NQN>` | Connect to subsystem (port 4420) |
| `nvme disconnect -n <NQN>` | Disconnect from subsystem |
| `nvme list-subsys` | List subsystems and paths |
| `cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy` | Check IO policy |
| `pvesm status` | Check Proxmox storage status |

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
- [Common Network Concepts]({% link _includes/network-concepts.md %})
- [Performance Tuning]({% link _includes/performance-tuning.md %})
- [Troubleshooting Guide]({% link _includes/troubleshooting-common.md %})
- [Storage Terminology Glossary]({% link _includes/glossary.md %})
