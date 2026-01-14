# NVMe-TCP on Proxmox VE - Quick Start Guide

Generic guide for configuring NVMe over TCP storage on Proxmox VE using native CLI tools.

## Prerequisites

- Proxmox VE 8.x or 9.x
- NVMe-TCP storage array with:
  - Portal IP address(es) and port (default: 8009)
  - Subsystem NQN
- Dedicated network interfaces for storage traffic (recommended)
- Network connectivity between Proxmox nodes and storage

## Step 1: Configure Network Interfaces (All Nodes)

For optimal performance and reliability, configure dedicated network interfaces for NVMe-TCP traffic.

### Option A: Dedicated Physical Interfaces (Recommended)

Use separate physical NICs for storage traffic. No VLAN tagging, direct connection to storage network. Replace `ens1f0np0` and `ens1f1np1` with your actual interface names.  Replace `192.168.100.10` and `192.168.101.10` with your actual host IP addresses.

#### GUI Configuration

On each Proxmox node go to:  Datacenter -> Nodes -> <node> -> System -> Network

Select the interface and click Edit.  Set the IP address and MTU to 9000 (or 1500 if jumbo frames are not supported.  This configuration is in the advanced section).  Enable Autostart.  Click OK.
Gateway configuration should not be necessary.  The interfaces should be on the same subnet as the storage endpoints.  If this is not the case manual routing will be necessary.

#### CLI Configuration

Edit `/etc/network/interfaces`:

```bash
# Storage interface 1 - dedicated physical NIC
auto ens1f0np0
iface ens1f0np0 inet static
    address 192.168.100.10/24
    mtu 9000

# Storage interface 2 - dedicated physical NIC
auto ens1f1np1
iface ens1f1np1 inet static
    address 192.168.101.10/24
    mtu 9000
```

### Option B: VLAN Interfaces on Physical NICs

If you need to share physical NICs, use VLAN interfaces. Replace `ens1f0` and `ens1f1` with your actual interface names, `192.168.100.10` and `192.168.101.10` with your actual host IP addresses, and `100` with your actual VLAN ID(s):

#### Load 8021q module if necessary.  On Proxmox this is already enabled on Proxmox VE
```bash
# Load 8021q module for VLANs
modprobe 8021q
echo "8021q" >> /etc/modules-load.d/vlans.conf
```

Edit `/etc/network/interfaces`:

```bash
# Physical interface (no IP, just up)
auto ens1f0
iface ens1f0 inet manual
    mtu 9000

# Storage VLAN 100 on ens1f0
auto ens1f0.100
iface ens1f0.100 inet static
    address 192.168.100.10/24
    vlan-raw-device ens1f0
    mtu 9000

# Physical interface 2 (no IP, just up)
auto ens1f1
iface ens1f1 inet manual
    mtu 9000

# Storage VLAN 101 on ens1f1
auto ens1f1.100
iface ens1f1.100 inet static
    address 192.168.100.11/24
    vlan-raw-device ens1f1
    mtu 9000
```

### Apply Network Configuration

```bash
# Apply changes
ifreload -a

# Verify interfaces are up
ip addr show ens1f1.100
ip addr show ens1f0.100

# Test connectivity to storage portals
ping -I ens1f0np0 <PORTAL_IP_1>
ping -I ens1f0np0 <PORTAL_IP_2>
ping -I ens1f1np1 <PORTAL_IP_1>
ping -I ens1f1np1 <PORTAL_IP_2>
```

### Network Design Notes

- **Jumbo frames (MTU 9000)**: Recommended for storage traffic. Ensure switches and storage support jumbo frames end-to-end.
- **Separate subnets**: Each storage path should be on a separate subnet for proper multipath isolation.
- **No bonding**: Do not bond storage interfaces. NVMe native multipath handles redundancy.

## Step 2: Install Dependencies (All Nodes)

Run on **every Proxmox node**:

```bash
# Install nvme-cli
apt-get update
apt-get install -y nvme-cli

# Load kernel modules
modprobe nvme
modprobe nvme-tcp
modprobe nvme-core

# Make modules load on boot
cat > /etc/modules-load.d/nvme-tcp.conf << 'EOF'
nvme
nvme-tcp
nvme-core
EOF

# Enable NVMe native multipath
echo 'Y' > /sys/module/nvme_core/parameters/multipath

# Make multipath persistent across reboots
echo 'options nvme_core multipath=Y' > /etc/modprobe.d/nvme-tcp.conf
```

## Step 2: Generate Host NQN (All Nodes)

```bash
# Create directory
mkdir -p /etc/nvme

# Generate host NQN if it doesn't exist
if [ ! -f /etc/nvme/hostnqn ]; then
    nvme gen-hostnqn > /etc/nvme/hostnqn
fi

# Display host NQN - register this with your storage array
cat /etc/nvme/hostnqn
```

**Important:** Add each node's host NQN to your storage array's allowed hosts list.

## Step 4: Discover Targets (Optional)

```bash
# Discover available NVMe subsystems via specific interface
nvme discover -t tcp \
    -a <PORTAL_IP_1> \
    -s 8009 \
    --host-iface=ens1f0np0 \
    --host-traddr=192.168.100.10
```

## Step 5: Connect to NVMe-TCP Target (All Nodes)

Run on **every Proxmox node**. Each interface connects to ALL portals for maximum path redundancy.
With 2 interfaces and 4 portals, you get 8 paths total.  Replace `<PORTAL_IP_X>` with your actual portal IP addresses, and `<SUBSYSTEM_NQN>` with your actual subsystem NQN.  Replace ens1f0np0 and ens1f1np1 with your actual interface names.  Replace 192.168.100.10 and 192.168.100.11 with your actual host IP addresses.  Replace 4420 with your actual port if different.  The example below assumes you have 4 portals.  If you have more or less, adjust accordingly.

```bash
# Interface 1 -> All Portals
nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0np0 --host-traddr=192.168.100.10 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0np0 --host-traddr=192.168.100.10 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_3> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0np0 --host-traddr=192.168.100.10 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_4> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f0np0 --host-traddr=192.168.100.10 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Interface 2 -> All Portals
nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1np1 --host-traddr=192.168.100.11 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1np1 --host-traddr=192.168.100.11 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_3> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1np1 --host-traddr=192.168.100.11 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

nvme connect -t tcp -a <PORTAL_IP_4> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=ens1f1np1 --host-traddr=192.168.100.11 \
    --ctrl-loss-tmo=1800 --reconnect-delay=10
```

Verify connection:
```bash
# List subsystems and paths (should show 8 paths)
nvme list-subsys

# List NVMe devices
nvme list

# Check block devices
lsblk | grep nvme
```

## Step 6: Configure IO Policy with udev (All Nodes)

Create a udev rule to automatically set the IO policy when NVMe subsystems are created:

```bash
# Create udev rule for NVMe IO policy
cat > /etc/udev/rules.d/99-nvme-iopolicy.rules << 'EOF'
# Set IO policy to queue-depth for all NVMe subsystems
ACTION=="add", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF

# Reload udev rules
udevadm control --reload-rules
udevadm trigger

# Apply to existing subsystems (for current session)
for subsys in /sys/class/nvme-subsystem/nvme-subsys*; do
    echo "queue-depth" > "$subsys/iopolicy" 2>/dev/null || true
done

# Verify
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
```

The udev rule ensures the IO policy is set automatically on every boot and whenever new subsystems are connected.

## Step 7: Configure Persistent Connections (All Nodes)

Use the native nvme-cli discovery configuration for automatic connections on boot.
Each interface connects to ALL portals for maximum redundancy (2 interfaces × 4 portals = 8 paths).

### Option A: Discovery Controller Configuration (Recommended)

Create a discovery configuration file:

```bash
# Create config directory
mkdir -p /etc/nvme

# Create discovery.conf - one entry per path (interface + portal combination)
# 2 interfaces x 4 portals = 8 entries
cat > /etc/nvme/discovery.conf << 'EOF'
# NVMe-TCP Discovery Configuration
# Each line defines one path: host interface -> storage portal
# Format: --transport=tcp --traddr=<portal> --trsvcid=<port> --host-iface=<iface> --host-traddr=<host-ip>

# Interface 1 -> All Portals
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10
--transport=tcp --traddr=<PORTAL_IP_3> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10
--transport=tcp --traddr=<PORTAL_IP_4> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10

# Interface 2 -> All Portals
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11
--transport=tcp --traddr=<PORTAL_IP_3> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11
--transport=tcp --traddr=<PORTAL_IP_4> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11
EOF
```

Enable and start the nvme-connect service:

```bash
# Enable automatic connection on boot
systemctl enable nvmf-autoconnect.service

# Connect now (discovers and connects to all subsystems via all paths)
nvme connect-all
```

### Option B: Per-Subsystem Configuration

For more control, create individual configuration files with explicit NQN and timeouts:

```bash
# Create config directory for subsystems
mkdir -p /etc/nvme/config.d

# Create a config file for your subsystem
# 2 interfaces x 4 portals = 8 paths
cat > /etc/nvme/config.d/my-storage.conf << 'EOF'
# Subsystem: my-storage
# 8 paths: 2 interfaces x 4 portals

# Interface 1 -> All Portals
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_3> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_4> --trsvcid=4420 --host-iface=ens1f0np0 --host-traddr=192.168.100.10 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10

# Interface 2 -> All Portals
--transport=tcp --traddr=<PORTAL_IP_1> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_2> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_3> --trsvcid=4420 --host-iface=ens1f1np1 --host-traddr=192.168.100.11 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
--transport=tcp --traddr=<PORTAL_IP_4> --trsvcid=8009 --host-iface=ens1f1np1 --host-traddr=192.168.100.11 --nqn=<SUBSYSTEM_NQN> --ctrl-loss-tmo=1800 --reconnect-delay=10
4420

# Enable automatic connection
systemctl enable nvmf-autoconnect.service

# Connect now
nvme connect-all
```

### Verify Persistent Configuration

```bash
# Check if service is enabled
systemctl is-enabled nvmf-autoconnect.service

# View current connections
nvme list-subsys

# Test by rebooting
reboot
```

After reboot, verify connections are restored:

```bash
nvme list-subsys
nvme list
```

## Step 7: Create LVM Volume Group (One Node)

Run on **one node only**:

```bash
# List NVMe namespaces
lsblk | grep nvme

# Create LVM physical volume (use your device)
pvcreate /dev/nvme0n1

# Create volume group
vgcreate nvme-vg /dev/nvme0n1

# Verify
vgs
pvs
```

## Step 8: Activate VG on Other Nodes

Run on **each additional node**:

```bash
pvscan --cache
vgscan
vgchange -ay nvme-vg
```

## Step 9: Add LVM Storage to Proxmox (One Node)

Run on **one node only** (config syncs via cluster):

```bash
# Add LVM storage
pvesm add lvm nvme-datastore \
    --vgname nvme-vg \
    --content images,rootdir \
    --shared 1

# Verify
pvesm status
```

## Verify Setup

```bash
# Check NVMe connections
nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check Proxmox storage
pvesm status

# Check LVM
vgs
lvs
```

---

## Quick Reference

| Command | Description |
|---------|-------------|
| `nvme list` | List NVMe devices |
| `nvme list-subsys` | List subsystems and paths |
| `nvme discover -t tcp -a <ip> -s 8009` | Discover targets |
| `nvme connect -t tcp -a <ip> -n <nqn>` | Connect to target |
| `nvme disconnect -n <nqn>` | Disconnect from target |
| `cat /sys/class/nvme-subsystem/*/iopolicy` | Check IO policy |

## Disconnect

```bash
# Disconnect from subsystem
nvme disconnect -n <NQN>

# Or disconnect all
nvme disconnect-all
```

---

For the automated plugin version, see [README.md](README.md).

