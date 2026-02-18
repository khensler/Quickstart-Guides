# iSCSI on SUSE/openSUSE - Quick Start Guide

Guide for configuring iSCSI storage on SUSE Linux Enterprise Server (SLES) and openSUSE systems.

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
- iSCSI storage array with:
  - Portal IP address(es) and port (default: 3260)
  - Target IQN (iSCSI Qualified Name)
  - Optional: CHAP authentication credentials
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Root or sudo access
- Active SUSE subscription (for SLES) or openSUSE repositories

## Key Terminology

> **📖 New to iSCSI?** See the complete [Storage Terminology Glossary](../../common/includes/glossary.md) for definitions of all terms used in this guide.

| Term | Definition |
|------|------------|
| **IQN** | iSCSI Qualified Name - unique identifier for initiators and targets (e.g., `iqn.2003-10.de.suse:server01`) |
| **Portal** | IP address and port combination for iSCSI access (e.g., `10.100.1.10:3260`) |
| **Target** | Storage array component that receives iSCSI connections |
| **Initiator** | Host-side component that initiates iSCSI connections |
| **LUN** | Logical Unit Number - individual storage volume presented to the host |
| **Multipath** | Multiple network paths between host and storage for redundancy |
| **CHAP** | Challenge-Handshake Authentication Protocol for iSCSI security |

> **⚠️ ARP Configuration Required for Same-Subnet Multipath**: When using multiple interfaces on the same subnet, proper ARP configuration (`arp_ignore=2`, `arp_announce=2`) is **critical** to prevent routing issues. See [ARP Configuration for Same-Subnet Multipath](../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath) for details.

## Step 1: Install Required Packages

```bash
# Update system
sudo zypper refresh
sudo zypper update -y

# Install iSCSI initiator and multipath
sudo zypper install -y open-iscsi multipath-tools

# Enable and start services
sudo systemctl enable --now iscsid
sudo systemctl enable --now multipathd
```

**Verify installation:**
```bash
# Check open-iscsi version
rpm -q open-iscsi

# Check services status
systemctl status iscsid
systemctl status multipathd
```

## Step 2: Configure Network Interfaces

### Using YaST (Recommended for SUSE)

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

### Using Wicked (SUSE Default)

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

## Step 3: Configure Firewall

### Using firewalld (SLES 15+/openSUSE Default)

```bash
# Check if firewalld is running
sudo systemctl status firewalld

# Allow iSCSI port
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
sudo sed -i 's/^# node.session.timeo.replacement_timeout = 120/node.session.timeo.replacement_timeout = 120/' /etc/iscsi/iscsid.conf
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

**Restart services to apply changes:**
```bash
sudo systemctl restart iscsid
```

## Step 5: Discover iSCSI Targets

### Discovery via Specific Interface

```bash
# Discover targets from first portal
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:3260

# Discover from second portal
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:3260

# Repeat for all portals
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
# Example (with recommended no_path_retry 0 configuration):
# mpatha (36000c29e3c2e8c5e5e5e5e5e5e5e5e5e) dm-0 PURE,FlashArray
# size=1.0T features='0' hwhandler='1 alua' wp=rw
# `-+- policy='service-time 0' prio=50 status=active
#   |- 2:0:0:1 sdb 8:16  active ready running
#   |- 3:0:0:1 sdc 8:32  active ready running
#   |- 4:0:0:1 sdd 8:48  active ready running
#   `- 5:0:0:1 sde 8:64  active ready running
#
# Note: features='0' indicates no_path_retry is configured (recommended)
# If you see features='1 queue_if_no_path', update multipath.conf to use
# no_path_retry 0 to prevent APD (All Paths Down) hangs

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

# Format filesystem (XFS recommended for SUSE)
sudo mkfs.xfs /dev/iscsi-storage/data

# Create mount point
sudo mkdir -p /mnt/iscsi-storage

# Mount
sudo mount /dev/iscsi-storage/data /mnt/iscsi-storage

# Add to /etc/fstab for persistence
echo '/dev/iscsi-storage/data /mnt/iscsi-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network and iSCSI are available.

**Alternative: Use Btrfs (SUSE default):**
```bash
# Install btrfsprogs if not present
sudo zypper install -y btrfsprogs

# Format with Btrfs
sudo mkfs.btrfs /dev/iscsi-storage/data

# Update fstab
echo '/dev/iscsi-storage/data /mnt/iscsi-storage btrfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

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

## Troubleshooting

### AppArmor Issues (SLES 15+)

If you encounter permission errors:

```bash
# Check AppArmor status
sudo aa-status

# Check for denials
sudo dmesg | grep -i apparmor | grep iscsi
sudo journalctl | grep -i apparmor | grep iscsi

# If needed, set to complain mode temporarily for testing
sudo aa-complain /usr/sbin/iscsid

# Test iSCSI connection
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP>:3260 --login

# Check for new denials
sudo dmesg | grep -i apparmor

# Enforce after testing
sudo aa-enforce /usr/sbin/iscsid
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

### Wicked Network Issues

```bash
# Check wicked status
sudo systemctl status wickedd

# Reload configuration
sudo wicked ifreload all

# Debug wicked
sudo wicked ifstatus --verbose all

# Check wicked logs
sudo journalctl -u wickedd -f
```

### YaST Configuration Issues

```bash
# Reconfigure with YaST
sudo yast2 lan

# Check YaST logs
sudo journalctl -u YaST2

# Reset network configuration
sudo yast lan delete id=0
sudo yast lan add name=ens1f0 bootproto=static ipaddr=10.100.1.101/24
```

### Subscription Issues (SLES)

```bash
# Check subscription status
sudo SUSEConnect --status

# Refresh subscriptions
sudo SUSEConnect --refresh

# Re-register if needed
sudo SUSEConnect -r <REGISTRATION_CODE>
```

## Additional Resources

- [SUSE Documentation](https://documentation.suse.com/)
- [openSUSE Wiki](https://en.opensuse.org/)
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

**YaST network configuration:**
```bash
sudo yast2 lan
```

**Wicked reload:**
```bash
sudo wicked ifreload all
```

## SUSE-Specific Notes

### SUSE Linux Enterprise Server (SLES)

- **Subscription required:** Use `SUSEConnect` to register
- **YaST:** Comprehensive system configuration tool (GUI/TUI/CLI)
- **Wicked:** Default network manager (more stable than NetworkManager for servers)
- **AppArmor:** Enabled by default in SLES 15+
- **Firewalld:** Default firewall in SLES 15+
- **Btrfs:** Default filesystem for root partition
- **Support:** Enterprise support available through SUSE

### openSUSE

- **Leap:** Stable release based on SLES (recommended for production)
- **Tumbleweed:** Rolling release (latest packages, less stable)
- **No subscription required:** Free to use
- **Same tools as SLES:** YaST, wicked, zypper
- **Community support:** Forums, mailing lists, IRC

### Network Management

**Wicked vs NetworkManager:**
- **Wicked (default):** Better for servers, more predictable, integrates with YaST
- **NetworkManager:** Better for desktops, can be installed if preferred

**Switch to NetworkManager (optional):**
```bash
# Install NetworkManager
sudo zypper install -y NetworkManager

# Disable wicked
sudo systemctl disable --now wicked

# Enable NetworkManager
sudo systemctl enable --now NetworkManager

# Use nmcli for configuration
sudo nmcli connection add type ethernet con-name storage-iscsi-1 \
    ifname ens1f0 ipv4.method manual ipv4.addresses 10.100.1.101/24 \
    802-3-ethernet.mtu 9000 connection.autoconnect yes
```

### Filesystem Recommendations

- **XFS:** Best for large files, high performance, recommended for storage workloads
- **Btrfs:** SUSE default, snapshots, compression, good for system volumes
- **ext4:** Traditional, reliable, good compatibility

For iSCSI storage workloads, **XFS is recommended** for best performance.

