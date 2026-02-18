# NVMe-TCP on Oracle Linux - Quick Start Guide

Guide for configuring NVMe over TCP storage on Oracle Linux with Unbreakable Enterprise Kernel (UEK).

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:**
> - This guide is **specific to Pure Storage configurations** and should be used in conjunction with official vendor documentation
> - Always consult and follow **Oracle Linux official documentation** for complete system configuration
> - In case of any conflicts between this guide and vendor documentation, **vendor documentation takes precedence**
>
> **Testing Requirements:**
> - All configurations and recommendations in this guide are **for reference only**
> - **Test thoroughly in a lab environment** before implementing in production
> - Validate all settings with your specific hardware, software versions, and workload requirements
> - Performance and compatibility may vary based on your environment
>
> **Support:**
> - For Pure Storage-specific issues, contact Pure Storage Support
> - For Oracle Linux issues, contact Oracle Support
> - This guide is provided as-is without warranty

---

## Prerequisites

- **Oracle Linux 8.x or 9.x**
- Kernel: **UEK R7** (5.15+) or **RHCK** (Red Hat Compatible Kernel)
- NVMe-TCP storage array with:
  - Portal IP address(es) and port (default: 4420)
  - Subsystem NQN (NVMe Qualified Name)
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Active Oracle Linux support subscription (optional but recommended)

## Key Terminology

> **📖 New to NVMe-TCP?** See the complete [Storage Terminology Glossary](../../../common/includes/glossary.md) for definitions of all terms used in this guide.

| Term | Definition |
|------|------------|
| **NQN** | NVMe Qualified Name - unique identifier for hosts and subsystems (e.g., `nqn.2014-08.org.nvmexpress:uuid:...`) |
| **Subsystem** | NVMe storage entity containing one or more namespaces (analogous to iSCSI target) |
| **Namespace** | Individual NVMe storage volume (analogous to iSCSI LUN) |
| **Portal** | IP address and port for NVMe-TCP access (data port: 4420, discovery: 8009) |
| **Host NQN** | Unique identifier for this host, stored in `/etc/nvme/hostnqn` |
| **Native Multipath** | Kernel-level multipathing for NVMe, enabled via `nvme_core multipath=Y` |
| **IO Policy** | Algorithm for selecting paths (queue-depth, round-robin, numa) |

> **⚠️ ARP Configuration Required for Same-Subnet Multipath**: When using multiple interfaces on the same subnet, proper ARP configuration (`arp_ignore=2`, `arp_announce=2`) is **critical** to prevent routing issues. See [ARP Configuration for Same-Subnet Multipath](../../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath) for details.

## Kernel Selection: UEK vs RHCK

Oracle Linux offers two kernel options:

### Unbreakable Enterprise Kernel (UEK) - Recommended
- **Latest features**: Newer kernel with latest NVMe improvements
- **Better performance**: Optimized for enterprise workloads
- **Ksplice support**: Zero-downtime kernel updates
- **Oracle support**: Full support from Oracle

### Red Hat Compatible Kernel (RHCK)
- **Compatibility**: Binary compatible with RHEL
- **Stability**: More conservative, proven in production
- **Use case**: When RHEL compatibility is required

**Check current kernel:**
```bash
uname -r
# UEK example: 5.15.0-100.96.32.el8uek.x86_64
# RHCK example: 4.18.0-477.27.1.el8_8.x86_64
```

**Switch to UEK (if not already):**
```bash
# Install UEK
sudo dnf install -y kernel-uek

# Set UEK as default
sudo grubby --set-default=/boot/vmlinuz-$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-uek | tail -1)

# Reboot
sudo reboot
```

## Step 1: Install Required Packages

```bash
# Update system
sudo dnf update -y

# Install NVMe CLI tools
sudo dnf install -y nvme-cli

# Install network tools
sudo dnf install -y NetworkManager-tui

# Optional: Install Oracle tools
sudo dnf install -y oracle-epel-release-el8
sudo dnf install -y sysstat iotop
```

**Verify installation:**
```bash
# Check nvme-cli version
nvme version

# Check kernel modules
lsmod | grep nvme

# Verify NVMe-TCP module is available
modinfo nvme-tcp
```

## Step 2: Configure Network Interfaces

### Using NetworkManager (nmcli) - Recommended

#### Dedicated Physical Interfaces

```bash
# Configure first storage interface
sudo nmcli connection add type ethernet \
    con-name storage-nvme-1 \
    ifname ens1f0 \
    ipv4.method manual \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Configure second storage interface
sudo nmcli connection add type ethernet \
    con-name storage-nvme-2 \
    ifname ens1f1 \
    ipv4.method manual \
    ipv4.addresses 10.100.2.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate connections
sudo nmcli connection up storage-nvme-1
sudo nmcli connection up storage-nvme-2

# Verify
nmcli connection show
ip addr show
```

#### VLAN Interfaces

```bash
# Ensure parent interface is up
sudo nmcli connection add type ethernet \
    con-name ens1f0 \
    ifname ens1f0 \
    ipv4.method disabled \
    ipv6.method disabled \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Create VLAN interface
sudo nmcli connection add type vlan \
    con-name storage-vlan100 \
    ifname ens1f0.100 \
    dev ens1f0 \
    id 100 \
    ipv4.method manual \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate
sudo nmcli connection up ens1f0
sudo nmcli connection up storage-vlan100
```

## Step 3: Configure Firewall

```bash
# Allow NVMe-TCP port (4420)
sudo firewall-cmd --permanent --add-port=4420/tcp

# Reload firewall
sudo firewall-cmd --reload

# Verify
sudo firewall-cmd --list-ports
```

**For zone-specific configuration:**
```bash
# Add storage interfaces to trusted zone
sudo firewall-cmd --permanent --zone=trusted --add-interface=ens1f0
sudo firewall-cmd --permanent --zone=trusted --add-interface=ens1f1

# Reload
sudo firewall-cmd --reload
```

## Step 4: Load NVMe-TCP Module

```bash
# Load module
sudo modprobe nvme-tcp

# Verify module is loaded
lsmod | grep nvme_tcp

# Make persistent
echo "nvme-tcp" | sudo tee /etc/modules-load.d/nvme-tcp.conf
```

## Step 5: Generate Host NQN

```bash
# Check if host NQN exists
cat /etc/nvme/hostnqn

# If not present, generate one
sudo nvme gen-hostnqn

# Verify
cat /etc/nvme/hostnqn
```

**Important:** Register this host NQN with your storage array's allowed hosts list.

## Step 6: Discover NVMe-TCP Targets

```bash
# Discover targets from storage portals
sudo nvme discover -t tcp -a <PORTAL_IP_1> -s 4420

# Example output:
# Discovery Log Number of Records 1, Generation counter 1
# =====Discovery Log Entry 0======
# trtype:  tcp
# adrfam:  ipv4
# subtype: nvme subsystem
# treq:    not specified
# portid:  0
# trsvcid: 4420
# subnqn:  nqn.2010-06.com.purestorage:flasharray.12345abc
# traddr:  10.100.1.10
```

## Step 7: Connect to NVMe-TCP Targets

### Manual Connection (All Paths)

Connect each host interface to all storage portals for full multipath redundancy.

**Example: 2 host interfaces × 4 storage portals = 8 paths**

```bash
# Connect via first interface to all portals
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0 --host-traddr=10.100.1.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0 --host-traddr=10.100.1.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_3> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0 --host-traddr=10.100.1.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_4> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0 --host-traddr=10.100.1.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Connect via second interface to all portals
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1 --host-traddr=10.100.2.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1 --host-traddr=10.100.2.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_3> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1 --host-traddr=10.100.2.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_4> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1 --host-traddr=10.100.2.101 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10
```

### Verify Connections

```bash
# List all NVMe subsystems and paths
sudo nvme list-subsys

# List NVMe devices
sudo nvme list

# Check connection status
sudo nvme list -v
```

## Step 8: Configure IO Policy

Set the IO policy to optimize path selection for your workload.

```bash
# Set IO policy to numa (recommended for most workloads)
for ctrl in /sys/class/nvme-subsystem/nvme-subsys*/iopolicy; do
    echo "numa" | sudo tee $ctrl
done

# Verify
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
```

**Create udev rule for persistence:**
```bash
sudo tee /etc/udev/rules.d/71-nvme-io-policy.rules > /dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="numa"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## Step 9: Configure Persistent Connections

### Using nvme-cli Discovery Configuration

```bash
# Create discovery configuration directory
sudo mkdir -p /etc/nvme/discovery.conf.d

# Create discovery configuration for each portal
sudo tee /etc/nvme/discovery.conf.d/portal1.conf > /dev/null <<EOF
-t tcp
-a <PORTAL_IP_1>
-s 4420
-w <INTERFACE_NAME_1>
-W <INTERFACE_IP_1>
-l 1800
-c 10
EOF

sudo tee /etc/nvme/discovery.conf.d/portal2.conf > /dev/null <<EOF
-t tcp
-a <PORTAL_IP_2>
-s 4420
-w <INTERFACE_NAME_1>
-W <INTERFACE_IP_1>
-l 1800
-c 10
EOF

# Repeat for all portal/interface combinations
```

### Enable nvmf-autoconnect Service

```bash
# Enable and start the service
sudo systemctl enable --now nvmf-autoconnect.service

# Verify service status
systemctl status nvmf-autoconnect.service

# Check logs
sudo journalctl -u nvmf-autoconnect.service
```

## Step 10: Create LVM Storage

```bash
# Find your NVMe device
sudo nvme list

# Create physical volume (use /dev/nvmeXnY)
sudo pvcreate /dev/nvme0n1

# Create volume group
sudo vgcreate nvme-storage /dev/nvme0n1

# Create logical volume (example: 500GB)
sudo lvcreate -L 500G -n data nvme-storage

# Format filesystem (XFS recommended)
sudo mkfs.xfs /dev/nvme-storage/data

# Create mount point
sudo mkdir -p /mnt/nvme-storage

# Mount
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to /etc/fstab for persistence
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network and NVMe-TCP are available.

## Step 11: Verify Configuration

```bash
# Check NVMe subsystems
sudo nvme list-subsys

# Check NVMe devices
sudo nvme list

# Check multipath status
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check LVM
sudo pvs
sudo vgs
sudo lvs

# Check mounted filesystems
df -h | grep nvme

# Test I/O performance
sudo dd if=/dev/zero of=/mnt/nvme-storage/testfile bs=1M count=1024 oflag=direct
sudo rm /mnt/nvme-storage/testfile
```

## Oracle Linux Specific Features

### Ksplice for Zero-Downtime Updates

If you have Oracle Linux Premier Support with Ksplice:

```bash
# Check Ksplice status
sudo uptrack-uname -r

# Apply kernel updates without reboot
sudo uptrack-upgrade -y

# Verify updates
sudo uptrack-show
```

**Note:** Ksplice allows you to apply kernel security updates without rebooting, maintaining NVMe-TCP connections.

### UEK-Specific Tuning

UEK includes optimizations for storage workloads:

```bash
# Check UEK version
uname -r

# View UEK-specific parameters
sysctl -a | grep uek

# UEK typically has better defaults for:
# - NVMe queue depth
# - TCP window scaling
# - Network buffer sizes
```

## Troubleshooting

### SELinux Issues

Oracle Linux has SELinux enabled by default:

```bash
# Check SELinux status
getenforce

# Check for denials
sudo ausearch -m avc -ts recent | grep nvme

# If needed, set to permissive temporarily for testing
sudo setenforce 0

# Test NVMe connection
sudo nvme connect -t tcp -a <PORTAL_IP> -s 4420 -n <SUBSYSTEM_NQN>

# Check for new denials
sudo ausearch -m avc -ts recent

# Generate and install policy
sudo ausearch -m avc -ts recent | audit2allow -M nvme_tcp_policy
sudo semodule -i nvme_tcp_policy.pp

# Re-enable enforcing
sudo setenforce 1
```

### Connection Failures

```bash
# Check firewall
sudo firewall-cmd --list-all

# Check network connectivity
ping <PORTAL_IP>
nc -zv <PORTAL_IP> 4420

# Check NVMe module
lsmod | grep nvme_tcp

# Check logs
sudo journalctl -k | grep nvme
sudo dmesg | grep nvme
```

### UEK vs RHCK Issues

If experiencing issues with UEK:

```bash
# Check current kernel
uname -r

# List available kernels
sudo grubby --info=ALL | grep title

# Switch to RHCK temporarily
sudo grubby --set-default=/boot/vmlinuz-<rhck-version>
sudo reboot

# Or switch back to UEK
sudo grubby --set-default=/boot/vmlinuz-<uek-version>
sudo reboot
```

## Additional Resources

- [Oracle Linux Documentation](https://docs.oracle.com/en/operating-systems/oracle-linux/)
- [UEK Release Notes](https://docs.oracle.com/en/operating-systems/uek/)
- [Ksplice Documentation](https://docs.oracle.com/en/operating-systems/ksplice/)
- [Best Practices Guide](./BEST-PRACTICES.md)
- [Common Network Concepts](../../../common/includes/network-concepts.md)
- [Performance Tuning](../../../common/includes/performance-tuning.md)
- [Troubleshooting Guide](../../../common/includes/troubleshooting-common.md)

## Quick Reference

**Discover targets:**
```bash
sudo nvme discover -t tcp -a <PORTAL_IP> -s 4420
```

**Connect to target:**
```bash
sudo nvme connect -t tcp -a <PORTAL_IP> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE> --host-traddr=<HOST_IP>
```

**Disconnect from target:**
```bash
sudo nvme disconnect -n <SUBSYSTEM_NQN>
```

**List subsystems:**
```bash
sudo nvme list-subsys
```

**Check IO policy:**
```bash
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
```

## Oracle Linux Specific Notes

- **UEK Recommended**: Use UEK R7 (5.15+) for best NVMe-TCP performance
- **Ksplice**: Enables zero-downtime kernel updates (requires Premier Support)
- **Binary Compatibility**: RHCK provides RHEL compatibility when needed
- **Oracle Support**: Full enterprise support available with subscription
- **Performance**: UEK typically provides 5-10% better storage performance than RHCK

