# NVMe-TCP on SUSE/openSUSE - Quick Start Guide

Guide for configuring NVMe over TCP storage on SUSE Linux Enterprise Server (SLES) and openSUSE systems.

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:**
> - This guide is **specific to Pure Storage configurations** and should be used in conjunction with official vendor documentation
> - Always consult and follow **SUSE/openSUSE official documentation** for complete system configuration
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
> - For SUSE/openSUSE issues, contact SUSE Support or community resources
> - This guide is provided as-is without warranty

---

## Prerequisites

- **SUSE Linux Enterprise Server (SLES) 15 SP3+** or **openSUSE Leap 15.3+** / **Tumbleweed**
- NVMe-TCP storage array with:
  - Portal IP address(es) and port (default: 4420)
  - Subsystem NQN
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Root or sudo access
- Active SUSE subscription (for SLES) or openSUSE repositories

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

## Step 1: Install Required Packages

```bash
# Update system
sudo zypper refresh
sudo zypper update -y

# Install NVMe tools
sudo zypper install -y nvme-cli
```

**Verify installation:**
```bash
# Check NVMe CLI version
nvme version

# Verify NVMe-TCP module is available
modinfo nvme-tcp
```

> **Note:** NVMe-TCP uses **native NVMe multipathing** built into the Linux kernel, not dm-multipath (device-mapper-multipath). The `multipath-tools` package is NOT needed for NVMe-TCP - it is only used for iSCSI and Fibre Channel.

## Step 2: Configure Network Interfaces

### Option A: Using YaST (Recommended for SUSE)

YaST is SUSE's comprehensive system configuration tool.

**GUI method:**
```bash
# Launch YaST network configuration
sudo yast2 lan

# Or use ncurses interface
sudo yast lan
```

**Steps in YaST:**
1. Select "Edit" on the storage interface
2. Set "Static Address Setup"
3. Enter IP address and netmask
4. Set MTU to 9000
5. Go to "Routing" tab
6. Uncheck "Set Default Gateway"
7. Save and apply

**Command-line YaST:**
```bash
# Configure first storage interface
sudo yast lan add name=ens1f0 \
    bootproto=static \
    ipaddr=10.100.1.101/24 \
    mtu=9000

# Configure second storage interface
sudo yast lan add name=ens1f1 \
    bootproto=static \
    ipaddr=10.100.2.101/24 \
    mtu=9000

# Apply configuration
sudo yast lan list
```

### Option B: Using Wicked (SUSE Default Network Manager)

Wicked is the default network configuration framework in SLES/openSUSE.

#### Dedicated Physical Interfaces

```bash
# Create configuration for first interface
sudo tee /etc/sysconfig/network/ifcfg-ens1f0 > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='10.100.1.101/24'
MTU='9000'
NAME='Storage Network 1'
EOF

# Create configuration for second interface
sudo tee /etc/sysconfig/network/ifcfg-ens1f1 > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='10.100.2.101/24'
MTU='9000'
NAME='Storage Network 2'
EOF

# Reload wicked configuration
sudo wicked ifreload all

# Verify
ip addr show
wicked ifstatus all
```

#### VLAN Interfaces

```bash
# Create parent interface config (no IP)
sudo tee /etc/sysconfig/network/ifcfg-ens1f0 > /dev/null <<EOF
BOOTPROTO='none'
STARTMODE='auto'
MTU='9000'
EOF

# Create VLAN interface config
sudo tee /etc/sysconfig/network/ifcfg-ens1f0.100 > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='10.100.1.101/24'
MTU='9000'
ETHERDEVICE='ens1f0'
VLAN_ID='100'
EOF

# Reload configuration
sudo wicked ifreload all
```

### Option C: Using NetworkManager (openSUSE Alternative)

**Note:** NetworkManager is available but not default on SLES. More common on openSUSE desktop.

```bash
# Install NetworkManager if needed
sudo zypper install -y NetworkManager

# Switch from wicked to NetworkManager (optional)
sudo systemctl disable --now wicked
sudo systemctl enable --now NetworkManager

# Configure interface
sudo nmcli connection add type ethernet \
    con-name storage-1 \
    ifname ens1f0 \
    ipv4.method manual \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate
sudo nmcli connection up storage-1
```

## Step 3: Configure Firewall

### Using firewalld (SLES 15+/openSUSE Default)

```bash
# Check if firewalld is running
sudo systemctl status firewalld

# Allow NVMe-TCP port
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

# Verify
sudo firewall-cmd --zone=trusted --list-all
```

### Using SuSEfirewall2 (Legacy SLES 12)

**Note:** SuSEfirewall2 is deprecated. Use firewalld on SLES 15+.

```bash
# Edit firewall configuration
sudo vi /etc/sysconfig/SuSEfirewall2

# Add to FW_SERVICES_EXT_TCP
FW_SERVICES_EXT_TCP="4420"

# Restart firewall
sudo systemctl restart SuSEfirewall2
```

## Step 4: Generate and Register Host NQN

```bash
# Generate host NQN if not exists
if [ ! -f /etc/nvme/hostnqn ]; then
    sudo mkdir -p /etc/nvme
    sudo nvme gen-hostnqn | sudo tee /etc/nvme/hostnqn
fi

# Display host NQN
cat /etc/nvme/hostnqn
```

**Important:** Register this host NQN with your storage array's allowed hosts list.

## Step 5: Discover NVMe Subsystems (Optional)

```bash
# Discover available subsystems via specific interface
sudo nvme discover -t tcp \
    -a <PORTAL_IP_1> \
    -s 4420 \
    --host-iface=<INTERFACE_NAME_1> \
    --host-traddr=<HOST_IP_1>

# Repeat for other portals/interfaces
```

## Step 6: Connect to NVMe Subsystems

### Manual Connection (All Paths)

Connect each host interface to each storage portal for full multipath redundancy.

**Example: 2 host interfaces × 4 storage portals = 8 paths**

```bash
# Interface 1 to all portals
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_3> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_4> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Interface 2 to all portals
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_2> --host-traddr=<HOST_IP_2> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# ... repeat for remaining portals
```

**Parameters explained:**
- `--ctrl-loss-tmo=1800` - Wait 30 minutes before giving up on reconnection
- `--reconnect-delay=10` - Wait 10 seconds between reconnection attempts
- `--host-iface` - Bind to specific network interface
- `--host-traddr` - Source IP address for connection

### Verify Connections

```bash
# List all NVMe devices
sudo nvme list

# Show subsystem topology with all paths
sudo nvme list-subsys

# Expected output shows multiple controllers (paths) per subsystem
```

## Step 7: Configure Native NVMe Multipath

NVMe-TCP uses **native NVMe multipathing** built into the Linux kernel. This is different from dm-multipath (used for iSCSI/FC) and provides lower latency and simpler configuration.

### Enable Native NVMe Multipath

```bash
# Enable native NVMe multipathing (must be done before connecting)
echo 'options nvme_core multipath=Y' | sudo tee /etc/modprobe.d/nvme-tcp.conf

# If module is already loaded, you need to reload it or reboot
# Option 1: Reboot (recommended for production)
sudo reboot

# Option 2: Reload modules (only if no NVMe devices in use)
# sudo modprobe -r nvme_tcp nvme_core
# sudo modprobe nvme_core
# sudo modprobe nvme_tcp
```

### Configure IO Policy with udev

Create a udev rule to automatically set the IO policy when NVMe subsystems are created:

```bash
# Create udev rule for NVMe IO policy
sudo tee /etc/udev/rules.d/99-nvme-iopolicy.rules > /dev/null <<'EOF'
# Set IO policy to queue-depth for all NVMe subsystems
ACTION=="add|change", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Apply to existing subsystems (for current session)
for subsys in /sys/class/nvme-subsystem/nvme-subsys*; do
    echo "queue-depth" | sudo tee "$subsys/iopolicy" 2>/dev/null || true
done
```

### Verify Native Multipath Configuration

```bash
# Check that native multipath is enabled
cat /sys/module/nvme_core/parameters/multipath
# Expected output: Y

# Check IO policy for all subsystems
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
# Expected output: queue-depth

# List all NVMe subsystems with paths
sudo nvme list-subsys

# Expected output shows multiple controllers (paths) per subsystem:
# nvme-subsys0 - NQN=nqn.2010-06.com.purestorage:flasharray...
#  +- nvme0 tcp traddr=10.100.1.10,trsvcid=4420 live
#  +- nvme1 tcp traddr=10.100.1.11,trsvcid=4420 live
#  +- nvme2 tcp traddr=10.100.2.10,trsvcid=4420 live
#  +- nvme3 tcp traddr=10.100.2.11,trsvcid=4420 live

# With native multipath, you see a single device per namespace
sudo nvme list
# Shows /dev/nvme0n1 (single device, kernel handles multipathing internally)
```

> **Important:** With native NVMe multipathing, the kernel presents a single `/dev/nvmeXnY` device per namespace and automatically handles path selection and failover. You do NOT use `/dev/mapper/` devices or `multipath -ll` commands - those are for dm-multipath (iSCSI/FC only).

## Step 8: Configure Persistent Connections

### Using systemd Service Files

Create systemd service for persistent connections:

```bash
# Create service directory
sudo mkdir -p /etc/systemd/system

# Create connection service template
sudo tee /etc/systemd/system/nvme-connect@.service > /dev/null <<'EOF'
[Unit]
Description=NVMe-TCP connection to %i
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/sbin/nvme connect -t tcp -a %i -s 4420 -n ${SUBSYSTEM_NQN} --ctrl-loss-tmo=1800 --reconnect-delay=10
ExecStop=/usr/sbin/nvme disconnect -n ${SUBSYSTEM_NQN}

[Install]
WantedBy=multi-user.target
EOF
```

### Using Discovery Service (Recommended)

```bash
# Create discovery configuration
sudo mkdir -p /etc/nvme
sudo tee /etc/nvme/discovery.conf > /dev/null <<EOF
# Discovery configuration for NVMe-TCP
-t tcp -a <PORTAL_IP_1> -s 4420
-t tcp -a <PORTAL_IP_2> -s 4420
-t tcp -a <PORTAL_IP_3> -s 4420
-t tcp -a <PORTAL_IP_4> -s 4420
EOF

# Enable and start discovery service
sudo systemctl enable nvmf-autoconnect.service
sudo systemctl start nvmf-autoconnect.service

# Verify service status
sudo systemctl status nvmf-autoconnect.service
```

### Using dracut for Early Boot (Optional)

For root on NVMe-TCP or early boot requirements:

```bash
# Add NVMe-TCP module to dracut
echo 'add_drivers+=" nvme-tcp "' | sudo tee /etc/dracut.conf.d/nvme-tcp.conf

# Rebuild initrd
sudo dracut -f

# Add kernel parameters (edit /etc/default/grub)
# Add to GRUB_CMDLINE_LINUX:
# rd.nvmf.hostnqn=<YOUR_HOST_NQN> rd.nvmf.discover=<PORTAL_IP>:4420

# Update grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
```

## Step 9: Create LVM Storage

```bash
# List NVMe devices (with native multipath, you see single device per namespace)
sudo nvme list
# Example output: /dev/nvme0n1

# Create physical volume using the NVMe device directly
sudo pvcreate /dev/nvme0n1

# Create volume group
sudo vgcreate nvme-storage /dev/nvme0n1

# Create logical volume (example: 500GB)
sudo lvcreate -L 500G -n data nvme-storage

# Format filesystem (XFS recommended for SUSE)
sudo mkfs.xfs /dev/nvme-storage/data

# Create mount point
sudo mkdir -p /mnt/nvme-storage

# Mount
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to /etc/fstab for persistence
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network is available.

> **Important:** With native NVMe multipathing, use `/dev/nvmeXnY` directly - NOT `/dev/mapper/mpathX`. The kernel handles multipathing internally.

**Alternative: Use Btrfs (SUSE default):**
```bash
# Format with Btrfs
sudo mkfs.btrfs /dev/nvme-storage/data

# Mount with Btrfs options
sudo mount -o defaults,_netdev /dev/nvme-storage/data /mnt/nvme-storage

# Update fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage btrfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 10: Verify Configuration

```bash
# Check NVMe connections and paths
sudo nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check native multipath is enabled
cat /sys/module/nvme_core/parameters/multipath

# Check LVM
sudo pvs
sudo vgs
sudo lvs

# Check mounted filesystems
df -h | grep nvme

# Test I/O
sudo dd if=/dev/zero of=/mnt/nvme-storage/testfile bs=1M count=1024 oflag=direct
sudo rm /mnt/nvme-storage/testfile
```

## Troubleshooting

### AppArmor Issues (SLES 15+/openSUSE)

If you encounter permission errors:

```bash
# Check AppArmor status
sudo aa-status

# Check for denials
sudo dmesg | grep -i apparmor
```

### Connection Failures

```bash
# Check firewall
sudo firewall-cmd --list-all

# Check network connectivity
ping <PORTAL_IP>
nc -zv <PORTAL_IP> 4420

# Check NVMe kernel module
lsmod | grep nvme

# Load module if needed
sudo modprobe nvme-tcp

# Check logs
sudo journalctl -u nvmf-autoconnect -f
sudo dmesg | grep nvme
```

### Native Multipath Not Working

```bash
# Check if native multipath is enabled
cat /sys/module/nvme_core/parameters/multipath
# Should show: Y

# If not enabled, check modprobe config
cat /etc/modprobe.d/nvme-tcp.conf
# Should contain: options nvme_core multipath=Y

# Check all paths are visible
sudo nvme list-subsys
# Each subsystem should show multiple controllers

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check for NVMe errors
sudo dmesg | grep -i nvme
```

> **Note:** NVMe-TCP does NOT use dm-multipath (`multipath -ll`, `multipathd`). Those tools are for iSCSI/FC only. Use `nvme list-subsys` to view NVMe paths.

### Wicked Network Issues

```bash
# Check wicked status
sudo systemctl status wickedd

# Reload network configuration
sudo wicked ifreload all

# Debug wicked
sudo wicked ifstatus --verbose all

# Check wicked logs
sudo journalctl -u wickedd
```

### YaST Issues

```bash
# Reconfigure network with YaST
sudo yast lan

# Check YaST logs
sudo journalctl -u YaST2
```

## Additional Resources

- [SUSE Documentation](https://documentation.suse.com/)
- [openSUSE Wiki](https://en.opensuse.org/Main_Page)
- [NVMe-TCP Best Practices](./BEST-PRACTICES.md)
- [Common Network Concepts](../../../common/includes/network-concepts.md)
- [Multipath Concepts](../../../common/includes/multipath-concepts.md)
- [Troubleshooting Guide](../../../common/includes/troubleshooting-common.md)

## Quick Reference

**Connect to subsystem:**
```bash
sudo nvme connect -t tcp -a <IP> -s 4420 -n <NQN> --ctrl-loss-tmo=1800
```

**List connections:**
```bash
sudo nvme list-subsys
```

**Disconnect:**
```bash
sudo nvme disconnect -n <NQN>
```

**Check paths (native NVMe multipath):**
```bash
sudo nvme list-subsys
```

**Check IO policy:**
```bash
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
```

**Reload network (wicked):**
```bash
sudo wicked ifreload all
```

## SUSE-Specific Notes

### SLES (SUSE Linux Enterprise Server)
- Enterprise-grade, commercial support available
- Uses wicked for network management by default
- YaST for system configuration
- AppArmor enabled by default (SLES 15+)
- Btrfs default filesystem
- Requires active subscription for updates

### openSUSE Leap
- Community-supported, based on SLES
- Same tools as SLES (wicked, YaST)
- Free to use
- Regular release cycle aligned with SLES

### openSUSE Tumbleweed
- Rolling release
- Latest packages
- Good for testing/development
- Not recommended for production storage

