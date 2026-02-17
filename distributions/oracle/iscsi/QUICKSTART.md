# iSCSI on Oracle Linux - Quick Start Guide

Guide for configuring iSCSI storage on Oracle Linux with Unbreakable Enterprise Kernel (UEK).

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
- iSCSI storage array with:
  - Portal IP address(es) and port (default: 3260)
  - Target IQN (iSCSI Qualified Name)
  - Optional: CHAP authentication credentials
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Active Oracle Linux support subscription (optional but recommended)

## Kernel Selection

Oracle Linux offers two kernel options. For iSCSI workloads:

**UEK (Recommended):**
- Better multipath performance
- Latest device-mapper features
- Ksplice support for zero-downtime updates

**RHCK:**
- RHEL compatibility
- Conservative, proven stability

**Check and switch to UEK:**
```bash
# Check current kernel
uname -r

# Install UEK if not present
sudo dnf install -y kernel-uek

# Set as default
sudo grubby --set-default=/boot/vmlinuz-$(rpm -q --qf '%{VERSION}-%{RELEASE}.%{ARCH}\n' kernel-uek | tail -1)

# Reboot
sudo reboot
```

## Step 1: Install Required Packages

```bash
# Update system
sudo dnf update -y

# Install iSCSI initiator and multipath
sudo dnf install -y iscsi-initiator-utils device-mapper-multipath

# Enable and start services
sudo systemctl enable --now iscsid
sudo systemctl enable --now multipathd
```

**Verify installation:**
```bash
# Check iSCSI initiator version
rpm -q iscsi-initiator-utils

# Check services status
systemctl status iscsid
systemctl status multipathd
```

## Step 2: Configure Network Interfaces

### Using NetworkManager (nmcli) - Recommended

#### Dedicated Physical Interfaces

```bash
# Configure first storage interface
sudo nmcli connection add type ethernet \
    con-name storage-iscsi-1 \
    ifname ens1f0 \
    ipv4.method manual \
    ipv4.addresses 10.100.1.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Configure second storage interface
sudo nmcli connection add type ethernet \
    con-name storage-iscsi-2 \
    ifname ens1f1 \
    ipv4.method manual \
    ipv4.addresses 10.100.2.101/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate connections
sudo nmcli connection up storage-iscsi-1
sudo nmcli connection up storage-iscsi-2

# Verify
nmcli connection show
ip addr show
```

#### VLAN Interfaces

```bash
# Ensure parent interface is up (no IP needed)
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
# Allow iSCSI port (3260)
sudo firewall-cmd --permanent --add-port=3260/tcp

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

## Step 4: Configure iSCSI Initiator

### Set Initiator Name

```bash
# View current initiator name
cat /etc/iscsi/initiatorname.iscsi

# Generate new initiator name if needed
echo "InitiatorName=$(iscsi-iname)" | sudo tee /etc/iscsi/initiatorname.iscsi

# Display initiator name
cat /etc/iscsi/initiatorname.iscsi
```

**Important:** Register this initiator IQN with your storage array's allowed initiators list.

### Configure iSCSI Daemon

```bash
# Edit iSCSI configuration
sudo nano /etc/iscsi/iscsid.conf

# Recommended settings:
# node.startup = automatic
# node.session.timeo.replacement_timeout = 120
# node.conn[0].timeo.noop_out_interval = 5
# node.conn[0].timeo.noop_out_timeout = 5
```

**Or use sed to update:**
```bash
sudo sed -i 's/^node.startup = manual/node.startup = automatic/' /etc/iscsi/iscsid.conf
sudo sed -i 's/^#node.session.timeo.replacement_timeout = 120/node.session.timeo.replacement_timeout = 120/' /etc/iscsi/iscsid.conf
```

### Configure CHAP Authentication (Optional)

If your storage array requires CHAP authentication:

```bash
# Edit iscsid.conf
sudo nano /etc/iscsi/iscsid.conf

# Uncomment and set:
# node.session.auth.authmethod = CHAP
# node.session.auth.username = <your_username>
# node.session.auth.password = <your_password>
```

**Or use sed:**
```bash
sudo sed -i 's/^#node.session.auth.authmethod = CHAP/node.session.auth.authmethod = CHAP/' /etc/iscsi/iscsid.conf
sudo sed -i "s/^#node.session.auth.username = username/node.session.auth.username = <your_username>/" /etc/iscsi/iscsid.conf
sudo sed -i "s/^#node.session.auth.password = password/node.session.auth.password = <your_password>/" /etc/iscsi/iscsid.conf
```

**Restart iscsid to apply changes:**
```bash
sudo systemctl restart iscsid
```

## Step 5: Discover iSCSI Targets

### Discovery via Specific Interface

```bash
# Discover targets from first portal via specific interface
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:3260 -I <INTERFACE_NAME_1>

# Discover from second portal
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:3260 -I <INTERFACE_NAME_2>

# Repeat for all portals and interfaces
```

**Example output:**
```
10.100.1.10:3260,1 iqn.2010-06.com.purestorage:flasharray.12345abc
10.100.1.11:3260,1 iqn.2010-06.com.purestorage:flasharray.12345abc
```

### View Discovered Targets

```bash
# List all discovered targets
sudo iscsiadm -m node

# Show detailed information
sudo iscsiadm -m node -P 1
```

## Step 6: Configure Interface Binding

Bind iSCSI sessions to specific network interfaces for multipath redundancy.

### Create iSCSI Interface Configurations

```bash
# Create interface configuration for first storage interface
sudo iscsiadm -m iface -I iface0 --op=new
sudo iscsiadm -m iface -I iface0 --op=update -n iface.net_ifacename -v ens1f0
sudo iscsiadm -m iface -I iface0 --op=update -n iface.ipaddress -v 10.100.1.101

# Create interface configuration for second storage interface
sudo iscsiadm -m iface -I iface1 --op=new
sudo iscsiadm -m iface -I iface1 --op=update -n iface.net_ifacename -v ens1f1
sudo iscsiadm -m iface -I iface1 --op=update -n iface.ipaddress -v 10.100.2.101

# Verify interface configurations
sudo iscsiadm -m iface
```

## Step 7: Login to iSCSI Targets

### Manual Login (All Paths)

Login to each target via each interface for full multipath redundancy.

**Example: 2 host interfaces × 4 storage portals = 8 paths**

```bash
# Login via first interface to all portals
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_3>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_4>:3260 -I iface0 --login

# Login via second interface to all portals
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface1 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface1 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_3>:3260 -I iface1 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_4>:3260 -I iface1 --login
```

### Set Automatic Login on Boot

```bash
# Set all sessions to automatic startup
sudo iscsiadm -m node -T <TARGET_IQN> --op=update -n node.startup -v automatic

# Or set for specific portal
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --op=update -n node.startup -v automatic
```

### Verify Sessions

```bash
# List active sessions
sudo iscsiadm -m session

# Detailed session information
sudo iscsiadm -m session -P 3

# Check discovered devices
lsblk
sudo lsscsi
```

## Step 8: Configure Multipath

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

# Example for generic iSCSI devices:
devices {
    device {
        vendor ".*"
        product ".*"
        path_selector "service-time 0"
        path_grouping_policy "group_by_prio"
        prio "alua"
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

# Expected output: Shows iSCSI LUNs with multiple paths
# Example:
# mpatha (36000c29e3c2e8c5e5e5e5e5e5e5e5e5e) dm-0 PURE,FlashArray
# size=1.0T features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
# `-+- policy='service-time 0' prio=50 status=active
#   |- 2:0:0:1 sdb 8:16  active ready running
#   |- 3:0:0:1 sdc 8:32  active ready running
#   |- 4:0:0:1 sdd 8:48  active ready running
#   `- 5:0:0:1 sde 8:64  active ready running

# Verify all paths are active
sudo multipath -ll | grep -E "status=active|status=enabled"
```

## Step 9: Configure Persistent Connections

### Enable iSCSI Services

```bash
# Enable iSCSI services to start on boot
sudo systemctl enable iscsid
sudo systemctl enable iscsi

# Verify services are enabled
systemctl is-enabled iscsid
systemctl is-enabled iscsi
```

### Verify Automatic Login Configuration

```bash
# Check that targets are set to automatic startup
sudo iscsiadm -m node -P 1 | grep "node.startup"

# Should show: node.startup = automatic

# If not, set it:
sudo iscsiadm -m node --op=update -n node.startup -v automatic
```

## Step 10: Create LVM Storage

```bash
# Find your multipath device
sudo multipath -ll

# Create physical volume (use /dev/mapper/mpathX)
sudo pvcreate /dev/mapper/mpatha

# Create volume group
sudo vgcreate iscsi-storage /dev/mapper/mpatha

# Create logical volume (example: 500GB)
sudo lvcreate -L 500G -n data iscsi-storage

# Format filesystem (XFS recommended for Oracle Linux)
sudo mkfs.xfs /dev/iscsi-storage/data

# Create mount point
sudo mkdir -p /mnt/iscsi-storage

# Mount
sudo mount /dev/iscsi-storage/data /mnt/iscsi-storage

# Add to /etc/fstab for persistence
echo '/dev/iscsi-storage/data /mnt/iscsi-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network and iSCSI are available.

## Step 11: Verify Configuration

```bash
# Check iSCSI sessions
sudo iscsiadm -m session

# Check multipath devices
sudo multipath -ll

# Check LVM
sudo pvs
sudo vgs
sudo lvs

# Check mounted filesystems
df -h | grep iscsi

# Test I/O
sudo dd if=/dev/zero of=/mnt/iscsi-storage/testfile bs=1M count=1024 oflag=direct
sudo rm /mnt/iscsi-storage/testfile
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

**Note:** Ksplice allows you to apply kernel security updates without rebooting, maintaining iSCSI connections.

### UEK-Specific Multipath Optimizations

UEK includes optimizations for device-mapper multipath:

```bash
# Check UEK version
uname -r

# UEK typically has better defaults for:
# - ALUA support
# - Path failover times
# - I/O scheduler integration
```

## Troubleshooting

### SELinux Issues

Oracle Linux has SELinux enabled by default:

```bash
# Check SELinux status
getenforce

# Check for denials
sudo ausearch -m avc -ts recent | grep iscsi

# If needed, set to permissive temporarily for testing
sudo setenforce 0

# Test iSCSI connection
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --login

# Check for new denials
sudo ausearch -m avc -ts recent

# Generate and install policy
sudo ausearch -m avc -ts recent | audit2allow -M iscsi_policy
sudo semodule -i iscsi_policy.pp

# Re-enable enforcing
sudo setenforce 1
```

### Connection Failures

```bash
# Check firewall
sudo firewall-cmd --list-all

# Check network connectivity
ping <PORTAL_IP>
nc -zv <PORTAL_IP> 3260

# Check iSCSI service
systemctl status iscsid

# Check logs
sudo journalctl -u iscsid -f
sudo journalctl -u iscsi -f
sudo dmesg | grep iscsi
```

### Login Errors

```bash
# Check initiator name is registered on storage array
cat /etc/iscsi/initiatorname.iscsi

# Check CHAP credentials if used
sudo grep -i chap /etc/iscsi/iscsid.conf

# Restart iSCSI services
sudo systemctl restart iscsid
sudo systemctl restart iscsi

# Try manual login with debug
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --login -d 8
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
- [iSCSI Best Practices](./BEST-PRACTICES.md)
- [Common Network Concepts](../../common/includes/network-concepts.md)
- [Multipath Concepts](../../common/includes/multipath-concepts.md)
- [Troubleshooting Guide](../../common/includes/troubleshooting-common.md)

## Quick Reference

**Discover targets:**
```bash
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP>:3260
```

**Login to target:**
```bash
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --login
```

**Logout from target:**
```bash
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --logout
```

**List sessions:**
```bash
sudo iscsiadm -m session
```

**Check multipath:**
```bash
sudo multipath -ll
```

**Reload multipath:**
```bash
sudo systemctl restart multipathd
```

## Oracle Linux Specific Notes

- **UEK Recommended**: Use UEK R7 (5.15+) for best iSCSI/multipath performance
- **Ksplice**: Enables zero-downtime kernel updates (requires Premier Support)
- **Binary Compatibility**: RHCK provides RHEL compatibility when needed
- **Oracle Support**: Full enterprise support available with subscription
- **Performance**: UEK typically provides better multipath failover times than RHCK
- **Device-Mapper**: UEK includes optimized device-mapper multipath implementation

