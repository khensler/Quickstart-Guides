# iSCSI on Debian/Ubuntu - Quick Start Guide

Guide for configuring iSCSI storage on Debian and Ubuntu systems.

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
- iSCSI storage array with:
  - Portal IP address(es) and port (default: 3260)
  - Target IQN (iSCSI Qualified Name)
  - Optional: CHAP authentication credentials
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between hosts and storage
- Root or sudo access

## Key Terminology

> **📖 New to iSCSI?** See the complete [Storage Terminology Glossary](../../common/includes/glossary.md) for definitions of all terms used in this guide.

| Term | Definition |
|------|------------|
| **IQN** | iSCSI Qualified Name - unique identifier for initiators and targets (e.g., `iqn.1993-08.org.debian:01:server01`) |
| **Portal** | IP address and port combination for iSCSI access (e.g., `10.100.1.10:3260`) |
| **Target** | Storage array component that receives iSCSI connections |
| **Initiator** | Host-side component that initiates iSCSI connections |
| **LUN** | Logical Unit Number - individual storage volume presented to the host |
| **Multipath** | Multiple network paths between host and storage for redundancy |
| **CHAP** | Challenge-Handshake Authentication Protocol for iSCSI security |

> **⚠️ ARP Configuration Required for Same-Subnet Multipath**: When using multiple interfaces on the same subnet, proper ARP configuration (`arp_ignore=2`, `arp_announce=2`) is **critical** to prevent routing issues. See [ARP Configuration for Same-Subnet Multipath](../../common/includes/network-concepts.md#arp-configuration-for-same-subnet-multipath) for details.

## Step 1: Install Required Packages

```bash
# Update package lists
sudo apt update

# Install iSCSI initiator and multipath
sudo apt install -y open-iscsi multipath-tools

# Enable and start services
sudo systemctl enable --now open-iscsi
sudo systemctl enable --now multipathd
```

**Verify installation:**
```bash
# Check open-iscsi version
dpkg -l | grep open-iscsi

# Check services status
systemctl status open-iscsi
systemctl status multipathd
```

## Step 2: Configure Network Interfaces

### Using Netplan (Ubuntu 18.04+, Debian 11+)

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
      dhcp4: no
      dhcp6: no
    
    # Second storage interface
    ens1f1:
      addresses:
        - 10.100.2.101/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
```

**Apply configuration:**
```bash
# Test configuration
sudo netplan try

# Apply permanently
sudo netplan apply

# Verify
ip addr show
```

### Using /etc/network/interfaces (Debian Traditional)

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

# Second storage interface
auto ens1f1
iface ens1f1 inet static
    address 10.100.2.101
    netmask 255.255.255.0
    mtu 9000
```

**Apply configuration:**
```bash
# Bring up interfaces
sudo ifup ens1f0
sudo ifup ens1f1

# Verify
ip addr show
```

## Step 3: Configure Firewall

### Using UFW (Ubuntu Default)

```bash
# Allow iSCSI port
sudo ufw allow 3260/tcp

# Or allow from specific subnet
sudo ufw allow from 10.100.1.0/24 to any port 3260 proto tcp

# Enable firewall if not already enabled
sudo ufw enable

# Verify
sudo ufw status
```

### Using iptables (Debian/Manual)

```bash
# Allow iSCSI port
sudo iptables -A INPUT -p tcp --dport 3260 -j ACCEPT

# Save rules
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
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
sudo systemctl restart open-iscsi
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
# Enable iSCSI service to start on boot
sudo systemctl enable open-iscsi

# Verify service is enabled
systemctl is-enabled open-iscsi
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

# Format filesystem
sudo mkfs.ext4 /dev/iscsi-storage/data

# Create mount point
sudo mkdir -p /mnt/iscsi-storage

# Mount
sudo mount /dev/iscsi-storage/data /mnt/iscsi-storage

# Add to /etc/fstab for persistence
echo '/dev/iscsi-storage/data /mnt/iscsi-storage ext4 defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

**Note:** The `_netdev` option ensures the filesystem is mounted after network and iSCSI are available.

**Ubuntu-Specific: Use XFS:**
```bash
# Install XFS tools
sudo apt install -y xfsprogs

# Format with XFS
sudo mkfs.xfs /dev/iscsi-storage/data

# Update fstab
echo '/dev/iscsi-storage/data /mnt/iscsi-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
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

### AppArmor Issues (Ubuntu)

If you encounter permission errors:

```bash
# Check AppArmor status
sudo aa-status

# Check for denials
sudo dmesg | grep -i apparmor | grep iscsi

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
sudo ufw status  # Ubuntu
sudo iptables -L -n  # Debian

# Check network connectivity
ping <PORTAL_IP>
nc -zv <PORTAL_IP> 3260

# Check iSCSI service
systemctl status open-iscsi

# Check logs
sudo journalctl -u open-iscsi -f
sudo dmesg | grep iscsi
```

### Login Errors

```bash
# Check initiator name is registered on storage array
cat /etc/iscsi/initiatorname.iscsi

# Check CHAP credentials if used
sudo grep -i chap /etc/iscsi/iscsid.conf

# Restart iSCSI service
sudo systemctl restart open-iscsi

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

## Distribution-Specific Notes

### Debian
- Uses traditional `/etc/network/interfaces` or netplan (11+)
- Package: `open-iscsi`
- AppArmor available but not enabled by default
- Uses `iptables` or `nftables` for firewall

### Ubuntu
- **Server:** Uses netplan by default
- **Desktop:** Uses NetworkManager
- Package: `open-iscsi`
- AppArmor enabled by default
- Uses UFW (Uncomplicated Firewall)
- LTS versions recommended for production (20.04, 22.04, 24.04)

