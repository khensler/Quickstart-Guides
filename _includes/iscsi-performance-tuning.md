> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## iSCSI Performance Tuning

### Network Performance Optimization

#### MTU Configuration (Jumbo Frames)

**Why use jumbo frames:**
- Reduces CPU overhead by lowering packet count and interrupt rate
- Improves throughput for large sequential I/O (actual gains vary by workload)
- Lowers interrupt rate
- Recommended for high-performance storage (validate with benchmarks)

**Configuration:**
```bash
# Set MTU 9000 on storage interfaces
ip link set eth0 mtu 9000
ip link set eth1 mtu 9000

# Verify
ip link show eth0 | grep mtu
```

**Important:** MTU must be 9000 end-to-end (host → switch → storage)

#### TCP Tuning

**Optimize TCP for storage traffic:**
```bash
# /etc/sysctl.d/99-iscsi-tuning.conf
# Increase TCP buffer sizes
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.rmem_default = 16777216
net.core.wmem_default = 16777216
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# Increase connection tracking
net.netfilter.nf_conntrack_max = 1048576

# Optimize for low latency
net.ipv4.tcp_low_latency = 1
net.ipv4.tcp_sack = 1
net.ipv4.tcp_timestamps = 1

# Connection queue sizes
net.core.netdev_max_backlog = 30000
net.core.somaxconn = 4096

# Apply settings
sysctl -p /etc/sysctl.d/99-iscsi-tuning.conf
```

#### Network Interface Tuning (Ring Buffers, RSS, Coalescing)

Tune the storage NIC hardware queues (adjust interface names to match your host):
```bash
# Increase ring buffer size (check current with: ethtool -g <iface>)
ethtool -G ens1f0 rx 4096 tx 4096

# Receive-side scaling: spread packet processing across CPUs
ethtool -L ens1f0 combined 8

# Interrupt coalescing: fewer interrupts for throughput
ethtool -C ens1f0 rx-usecs 100 tx-usecs 100
# ...or minimize latency (more interrupts):
# ethtool -C ens1f0 rx-usecs 0 tx-usecs 0
```

> **Tip:** `ethtool` changes are not persistent. Apply them at boot with a systemd oneshot or your distro's network hooks. (The Proxmox iSCSI guide includes a ready-made `tune-storage-nics` service.)

### iSCSI Session Tuning

#### Queue Depth and Session Command Slots

These are two caps at different layers. Whichever is tighter is the one that binds.

- **`node.session.cmds_max`** — in-flight commands for the whole *session*, shared by
  every LUN on it. Open-iscsi preallocates this many task slots at login and uses the
  value as the SCSI host's `can_queue`. Must be a power of 2.
- **`node.session.queue_depth`** — the per-LUN cap (`cmd_per_lun`), applied to each `sd`
  device the session discovers. This is what `/sys/block/<dev>/device/queue_depth` reports.

With **L** LUNs on a session:

- `L × queue_depth < cmds_max` — the per-LUN cap binds, and raising `cmds_max` changes nothing.
- `L × queue_depth > cmds_max` — the session cap binds. That is a legitimate choice, but
  per-LUN depth is no longer a fairness guarantee: one busy volume can take most of the
  session's slots and the rest queue behind it.

**Multipath multiplies both.** With software iSCSI each session is its own SCSI host, so
every path carries a full `cmds_max`, and each LUN appears once per session with its own
`queue_depth`. Four paths at `queue_depth = 32` is **128 outstanding commands per volume**,
not 32 — which is why the per-path number looks smaller than you might expect.

**Sizing:**

1. Count LUNs per session and paths per LUN.
2. Take the per-volume concurrency the workload needs, divide by path count → `queue_depth`.
3. Set `cmds_max` at or above `L × queue_depth` — above it to let bursty LUNs borrow
   slots, at it for isolation between them.

| Topology | `queue_depth` | `cmds_max` |
|---|---|---|
| Multipathed flash (2-4 paths) | 32 | 128 |
| Single path, or few LUNs per session | 128 | 128-256 |

Don't simply maximise both. `cmds_max` preallocates memory per session, and queue depth
buys throughput only up to saturation — past that it converts directly into latency, and
overrunning what the array port accepts earns TASK SET FULL responses instead of I/O.

**Configuration:**
```bash
# /etc/iscsi/iscsid.conf
node.session.cmds_max = 128
node.session.queue_depth = 32

# Per-device at runtime
echo 32 > /sys/block/sda/device/queue_depth

# Make persistent via udev rule (adjust vendor to match your storage)
# /etc/udev/rules.d/99-iscsi-queue-depth.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{device/vendor}=="VENDOR*", ATTR{device/queue_depth}="32"
```

**Verify what is actually in force** — not what the config file says:
```bash
# Session parameters as negotiated
iscsiadm -m session -P 2

# Per-device depth the SCSI layer applied
cat /sys/block/sda/device/queue_depth
```

> **⚠️ `iscsid.conf` applies to new node records only.** Existing records under
> `/var/lib/iscsi/nodes/` keep the values baked in at discovery, so editing the file and
> restarting `iscsid` changes nothing for targets you have already discovered. Update a
> live target in place instead, then log out and back in:
>
> ```bash
> iscsiadm -m node -T <target_iqn> -p <portal_ip> \
>     -o update -n node.session.queue_depth -v 32
> ```

> **Note:** Offload HBAs (`be2iscsi`, `qla4xxx`, `bnx2i`) share a single SCSI host across
> sessions, with `can_queue` fixed by the adapter. `cmds_max` does not carve up per session
> on those, so the per-session arithmetic above does not apply.

#### Session Parameters

**Optimize iSCSI session settings:**
```bash
# Increase max receive data segment length
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.conn[0].iscsi.MaxRecvDataSegmentLength -v 262144

# Increase first burst length
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.iscsi.FirstBurstLength -v 262144

# Increase max burst length
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.iscsi.MaxBurstLength -v 1048576

# Enable immediate data
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.conn[0].iscsi.ImmediateData -v Yes

# Increase number of outstanding R2Ts
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.iscsi.MaxOutstandingR2T -v 1
```

### I/O Scheduler Optimization

**For SSD/Flash storage:**
```bash
# Use 'none' or 'noop' scheduler for flash storage
echo none > /sys/block/sda/queue/scheduler

# Make persistent via udev rule
# /etc/udev/rules.d/99-iscsi-scheduler.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/rotational}=="0", ATTR{queue/scheduler}="none"
```

**For HDD storage:**
```bash
# Use 'mq-deadline' for HDD
echo mq-deadline > /sys/block/sda/queue/scheduler
```

### CPU and IRQ Optimization

#### IRQ Affinity

**Distribute interrupts across CPUs:**
```bash
# Install irqbalance
# RHEL/Rocky/AlmaLinux:
dnf install -y irqbalance

# Debian/Ubuntu:
apt install -y irqbalance

# Enable and start
systemctl enable --now irqbalance

# Or manually set IRQ affinity
# Find IRQ for network interface
grep eth0 /proc/interrupts

# Set IRQ to specific CPU (example: IRQ 45 to CPU 2)
echo 4 > /proc/irq/45/smp_affinity  # 4 = binary 0100 = CPU 2
```

#### CPU Isolation (Advanced)

**Dedicate CPUs to storage I/O:**
```bash
# Edit kernel boot parameters
# /etc/default/grub
GRUB_CMDLINE_LINUX="isolcpus=2,3,10,11"

# Update grub
# RHEL/Rocky/AlmaLinux:
grub2-mkconfig -o /boot/grub2/grub.cfg

# Debian/Ubuntu:
update-grub

# Reboot required
reboot
```

> **⚠️ Note:** CPU isolation (`isolcpus`) is a general system optimization for I/O-intensive workloads. It does not directly affect iSCSI protocol behavior. Measure baseline performance before and after changes to validate impact in your environment.

#### Memory Configuration

**Hugepages for large I/O buffers:**
```bash
# /etc/sysctl.d/99-storage-performance.conf
vm.nr_hugepages = 1024

# Transparent hugepages (alternative)
echo always > /sys/kernel/mm/transparent_hugepage/enabled
```

**Disable NUMA balancing for predictable latency:**
```bash
echo 0 > /proc/sys/kernel/numa_balancing
```

### Read-Ahead Tuning

**Optimize read-ahead for workload:**
```bash
# Check current read-ahead
blockdev --getra /dev/sda

# For random I/O workloads (databases):
blockdev --setra 256 /dev/sda  # 128 KB

# For sequential I/O workloads (file servers):
blockdev --setra 8192 /dev/sda  # 4 MB

# Make persistent via udev rule (adjust vendor to match your storage)
# /etc/udev/rules.d/99-iscsi-readahead.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{device/vendor}=="VENDOR*", ATTR{bdi/read_ahead_kb}="128"
```

### Monitoring Performance

**Key metrics to monitor:**
```bash
# I/O statistics
iostat -x 1

# Network statistics
sar -n DEV 1

# iSCSI session statistics
iscsiadm -m session -P 3 | grep -A 20 "iSCSI Session State"

# Multipath I/O statistics
dmsetup status

# System-wide I/O
vmstat 1
```

**Performance indicators:**
- **Low latency**: < 1ms for flash storage
- **High throughput**: Near line speed (10Gbps = ~1.2 GB/s)
- **Low CPU wait**: iowait < 5%
- **Balanced paths**: Even I/O distribution across all paths

