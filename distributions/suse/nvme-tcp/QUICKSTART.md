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

## Step 1: Install Required Packages

```bash
# Update system
sudo zypper refresh
sudo zypper update -y

# Install NVMe tools and multipath
sudo zypper install -y nvme-cli multipath-tools

# Enable and start multipathd
sudo systemctl enable --now multipathd
```

**Verify installation:**
```bash
# Check NVMe CLI version
nvme version

# Check multipathd status
systemctl status multipathd
```

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

## Step 7: Configure Multipath

### Create Multipath Configuration

```bash
# Backup existing config if present
sudo cp /etc/multipath.conf /etc/multipath.conf.bak 2>/dev/null || true

# Create multipath configuration
sudo tee /etc/multipath.conf > /dev/null <<'EOF'
defaults {
    user_friendly_names yes
    find_multipaths no
    enable_foreign "^$"
}

blacklist {
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^hd[a-z]"
    devnode "^cciss.*"
}

# Add your storage vendor configuration here
# Example for Pure Storage:
devices {
    device {
        vendor "PURE"
        product "FlashArray"
        path_selector "service-time 0"
        path_grouping_policy "group_by_prio"
        prio "alua"
        failback "immediate"
        path_checker "tur"
        fast_io_fail_tmo 10
        dev_loss_tmo 60
        no_path_retry 0
        hardware_handler "1 alua"
        rr_min_io_rq 1
    }
}

# Example for generic NVMe devices:
devices {
    device {
        vendor "NVME"
        product ".*"
        path_selector "service-time 0"
        path_grouping_policy "group_by_prio"
        prio "ana"
        failback "immediate"
        no_path_retry 30
    }
}
EOF

# Restart multipathd to apply configuration
sudo systemctl restart multipathd

# Verify multipath devices
sudo multipath -ll
```

### Verify Multipath Configuration

```bash
# Check multipath status
sudo multipath -ll

# Expected output: Shows NVMe namespaces with multiple paths
# Example:
# mpatha (36000c29e3c2e8c5e5e5e5e5e5e5e5e5e) dm-0 NVME,Pure Storage FlashArray
# size=1.0T features='1 queue_if_no_path' hwhandler='0' wp=rw
# `-+- policy='service-time 0' prio=50 status=active
#   |- 0:1:1 nvme0n1 259:0 active ready running
#   |- 1:2:1 nvme1n1 259:1 active ready running
#   |- 2:3:1 nvme2n1 259:2 active ready running
#   `- 3:4:1 nvme3n1 259:3 active ready running

# Verify all paths are active
sudo multipath -ll | grep -E "status=active|status=enabled"
```

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
# Find your multipath device
sudo multipath -ll

# Create physical volume (use /dev/mapper/mpathX)
sudo pvcreate /dev/mapper/mpatha

# Create volume group
sudo vgcreate nvme-storage /dev/mapper/mpatha

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
# Check NVMe connections
sudo nvme list-subsys

# Check multipath devices
sudo multipath -ll

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

# If needed, set to complain mode temporarily for testing
sudo aa-complain /usr/sbin/multipathd

# Make permanent (not recommended for production)
sudo ln -s /etc/apparmor.d/usr.sbin.multipathd /etc/apparmor.d/disable/
sudo apparmor_parser -R /etc/apparmor.d/usr.sbin.multipathd
```

**Better approach:** Create AppArmor profile for NVMe-TCP if needed.

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

### Multipath Not Working

```bash
# Restart multipathd
sudo systemctl restart multipathd

# Reload configuration
sudo multipath -r

# Check for blacklisted devices
sudo multipath -v3

# Verify device-mapper
sudo dmsetup ls
```

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

**Check multipath:**
```bash
sudo multipath -ll
```

**Reload multipath:**
```bash
sudo systemctl restart multipathd
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

