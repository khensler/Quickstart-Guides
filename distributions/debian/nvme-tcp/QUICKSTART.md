# NVMe-TCP on Debian/Ubuntu - Quick Start Guide

Guide for configuring NVMe over TCP storage on Debian and Ubuntu systems.

---

## ⚠️ Important Disclaimers

> **Vendor Documentation Priority:**
> - This guide is **specific to Pure Storage configurations** and should be used in conjunction with official vendor documentation
> - Always consult and follow **Debian/Ubuntu official documentation** for complete system configuration
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
> - For Debian/Ubuntu issues, consult official documentation or community resources
> - This guide is provided as-is without warranty

---

## Prerequisites

- **Debian 11 (Bullseye)** or later, **Ubuntu 20.04 LTS** or later
- NVMe-TCP storage array with:
  - Portal IP address(es) and port (default: 4420)
  - Subsystem NQN
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Root or sudo access

## Key Terminology

> **📖 New to NVMe-TCP?** See the complete [Storage Terminology Glossary](../../common/includes/glossary.md) for definitions of all terms used in this guide.

| Term | Definition |
|------|------------|
| **NQN** | NVMe Qualified Name - unique identifier for hosts and subsystems (e.g., `nqn.2014-08.org.nvmexpress:uuid:...`) |
| **Subsystem** | NVMe storage entity containing one or more namespaces (analogous to iSCSI target) |
| **Namespace** | Individual NVMe storage volume (analogous to iSCSI LUN) |
| **Portal** | IP address and port for NVMe-TCP access (data port: 4420, discovery: 8009) |
| **Host NQN** | Unique identifier for this host, stored in `/etc/nvme/hostnqn` |
| **Native Multipath** | Kernel-level multipathing for NVMe, enabled via `nvme_core multipath=Y` |
| **IO Policy** | Algorithm for selecting paths (queue-depth, round-robin, numa) |

> **⚠️ ARP Configuration Required for Same-Subnet Multipath**: When using multiple interfaces on the same subnet, proper ARP configuration (`arp_ignore=2`, `arp_announce=2`) is **critical** to prevent routing issues. See [ARP Configuration for Same-Subnet Multipath](../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath) for details.

## Step 1: Install Required Packages

```bash
# Update package lists
sudo apt update

# Install NVMe tools
sudo apt install -y nvme-cli
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

### Option A: Using Netplan (Ubuntu 18.04+, Debian 11+)

Netplan is the default network configuration tool in modern Ubuntu and newer Debian versions.

#### Dedicated Physical Interfaces

```bash
# Edit netplan configuration
sudo nano /etc/netplan/50-storage.yaml
```

**Add configuration:**
```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    # First storage interface
    ens1f0:
      addresses:
        - 10.100.1.101/24
      mtu: 9000
      routes:
        - to: 10.100.1.0/24
          via: 0.0.0.0
          metric: 100
      routing-policy:
        - from: 10.100.1.101
          table: 100
      dhcp4: no
      dhcp6: no
    
    # Second storage interface
    ens1f1:
      addresses:
        - 10.100.2.101/24
      mtu: 9000
      routes:
        - to: 10.100.2.0/24
          via: 0.0.0.0
          metric: 100
      routing-policy:
        - from: 10.100.2.101
          table: 101
      dhcp4: no
      dhcp6: no
```

**Apply configuration:**
```bash
# Test configuration (will revert after 120 seconds if not confirmed)
sudo netplan try

# If successful, apply permanently
sudo netplan apply

# Verify
ip addr show
```

#### VLAN Interfaces

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    # Parent interface (no IP)
    ens1f0:
      dhcp4: no
      dhcp6: no
      mtu: 9000
  
  vlans:
    # VLAN 100 for storage
    ens1f0.100:
      id: 100
      link: ens1f0
      addresses:
        - 10.100.1.101/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
```

### Option B: Using /etc/network/interfaces (Debian Traditional)

For Debian systems using traditional networking:

```bash
# Edit interfaces file
sudo nano /etc/network/interfaces
```

**Add configuration:**
```
# First storage interface
auto ens1f0
iface ens1f0 inet static
    address 10.100.1.101
    netmask 255.255.255.0
    mtu 9000
    post-up ip route add 10.100.1.0/24 dev ens1f0 metric 100 || true

# Second storage interface
auto ens1f1
iface ens1f1 inet static
    address 10.100.2.101
    netmask 255.255.255.0
    mtu 9000
    post-up ip route add 10.100.2.0/24 dev ens1f1 metric 100 || true
```

**Apply configuration:**
```bash
# Bring up interfaces
sudo ifup ens1f0
sudo ifup ens1f1

# Verify
ip addr show
```

### Ubuntu-Specific: NetworkManager

**Note:** Ubuntu Desktop uses NetworkManager by default. For servers, use netplan (Option A).

If using NetworkManager:
```bash
# Create connection
nmcli connection add type ethernet \
    con-name storage-1 \
    ifname ens1f0 \
    ipv4.method manual \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate
nmcli connection up storage-1
```

## Step 3: Configure Firewall

### Using UFW (Ubuntu Default)

```bash
# Allow NVMe-TCP port
sudo ufw allow 4420/tcp

# Or allow from specific subnet
sudo ufw allow from 10.100.1.0/24 to any port 4420 proto tcp

# Enable firewall if not already enabled
sudo ufw enable

# Verify
sudo ufw status
```

### Using iptables (Debian/Manual)

```bash
# Allow NVMe-TCP port
sudo iptables -A INPUT -p tcp --dport 4420 -j ACCEPT

# Save rules (Debian)
sudo apt install -y iptables-persistent
sudo netfilter-persistent save

# Or save manually
sudo sh -c "iptables-save > /etc/iptables/rules.v4"
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

### Using initramfs for Early Boot (Optional)

For root on NVMe-TCP or early boot requirements:

**Debian:**
```bash
# Add NVMe-TCP module to initramfs
echo "nvme-tcp" | sudo tee -a /etc/initramfs-tools/modules

# Rebuild initramfs
sudo update-initramfs -u

# Add kernel parameters (edit /etc/default/grub)
# Add to GRUB_CMDLINE_LINUX:
# rd.nvmf.hostnqn=<YOUR_HOST_NQN> rd.nvmf.discover=<PORTAL_IP>:4420

# Update grub
sudo update-grub
```

**Ubuntu:**
```bash
# Same as Debian
echo "nvme-tcp" | sudo tee -a /etc/initramfs-tools/modules
sudo update-initramfs -u

# Update grub
sudo update-grub
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

# Format filesystem
sudo mkfs.ext4 /dev/nvme-storage/data

# Create mount point
sudo mkdir -p /mnt/nvme-storage

# Mount
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to /etc/fstab for persistence
echo '/dev/nvme-storage/data /mnt/nvme-storage ext4 defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network is available.

> **Important:** With native NVMe multipathing, use `/dev/nvmeXnY` directly - NOT `/dev/mapper/mpathX`. The kernel handles multipathing internally.

**Ubuntu-Specific:** You can also use XFS:
```bash
# Install XFS tools
sudo apt install -y xfsprogs

# Format with XFS
sudo mkfs.xfs /dev/nvme-storage/data
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

### AppArmor Issues (Ubuntu)

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
sudo ufw status  # Ubuntu
sudo iptables -L -n  # Debian

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

### Netplan Issues (Ubuntu)

```bash
# Debug netplan configuration
sudo netplan --debug apply

# Check networkd status
sudo systemctl status systemd-networkd

# View networkd logs
sudo journalctl -u systemd-networkd
```

## Additional Resources

- [Debian Administrator's Handbook](https://debian-handbook.info/)
- [Ubuntu Server Guide](https://ubuntu.com/server/docs)
- [NVMe-TCP Best Practices](./BEST-PRACTICES.md)
- [Common Network Concepts](../../common/includes/network-concepts.md)
- [Multipath Concepts](../../common/includes/multipath-concepts.md)
- [Troubleshooting Guide](../../common/includes/troubleshooting-common.md)

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

## Distribution-Specific Notes

### Debian
- Uses traditional `/etc/network/interfaces` or netplan (11+)
- AppArmor available but not enabled by default
- Uses `iptables` or `nftables` for firewall

### Ubuntu
- **Server:** Uses netplan by default
- **Desktop:** Uses NetworkManager
- AppArmor enabled by default
- Uses UFW (Uncomplicated Firewall) wrapper around iptables
- LTS versions recommended for production (20.04, 22.04, 24.04)

