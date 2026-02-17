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

## Step 1: Install Required Packages

```bash
# Update package lists
sudo apt update

# Install NVMe tools and multipath
sudo apt install -y nvme-cli multipath-tools

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
# Find your multipath device
sudo multipath -ll

# Create physical volume (use /dev/mapper/mpathX)
sudo pvcreate /dev/mapper/mpatha

# Create volume group
sudo vgcreate nvme-storage /dev/mapper/mpatha

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

**Ubuntu-Specific:** You can also use XFS:
```bash
# Install XFS tools
sudo apt install -y xfsprogs

# Format with XFS
sudo mkfs.xfs /dev/nvme-storage/data
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

### AppArmor Issues (Ubuntu)

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

**Check multipath:**
```bash
sudo multipath -ll
```

**Reload multipath:**
```bash
sudo systemctl restart multipathd
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

