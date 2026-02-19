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

# Apply settings
sysctl -p /etc/sysctl.d/99-iscsi-tuning.conf
```

### iSCSI Session Tuning

#### Queue Depth

**Increase queue depth for better performance:**
```bash
# Check current queue depth
cat /sys/block/sda/device/queue_depth

# Increase queue depth (per device)
echo 128 > /sys/block/sda/device/queue_depth

# Make persistent via udev rule (adjust vendor to match your storage)
# /etc/udev/rules.d/99-iscsi-queue-depth.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{device/vendor}=="VENDOR*", ATTR{device/queue_depth}="128"
```

**Recommended values:**
- **SSD/Flash storage**: 128-256
- **HDD storage**: 32-64

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

