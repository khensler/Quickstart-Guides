# Performance Tuning (iSCSI)

## System-Level Optimizations

### CPU Isolation for I/O Threads

**Isolate CPUs for storage processing:**
```bash
# In /etc/default/grub, add to GRUB_CMDLINE_LINUX:
GRUB_CMDLINE_LINUX="isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3"
```

> **⚠️ Note:** CPU isolation (`isolcpus`) is a general system optimization for I/O-intensive workloads. It does not directly affect iSCSI protocol behavior. Measure baseline performance before and after changes to validate impact in your environment.

**Best Practice:**
- Use `isolcpus` only if CPU contention is observed (high `%sys` during I/O)
- Monitor with `mpstat -P ALL 1` to identify busy cores

### Memory Configuration

**Hugepages for large I/O buffers:**
```bash
# /etc/sysctl.d/99-storage-performance.conf
vm.nr_hugepages = 1024

# For transparent hugepages (alternative)
echo always > /sys/kernel/mm/transparent_hugepage/enabled
```

**Disable NUMA balancing for predictable latency:**
```bash
echo 0 > /proc/sys/kernel/numa_balancing
```

## Network Optimizations

### TCP Buffer Tuning

**Increase TCP buffer sizes for high throughput:**
```bash
# /etc/sysctl.d/99-storage-tcp.conf

# TCP buffer sizes (min, default, max)
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# Connection queue sizes
net.core.netdev_max_backlog = 30000
net.core.somaxconn = 4096
```

### Network Interface Tuning

**Increase ring buffer size:**
```bash
# Check current settings
ethtool -g ens1f0

# Increase to maximum
ethtool -G ens1f0 rx 4096 tx 4096
```

**Enable receive-side scaling (RSS):**
```bash
# Check RSS configuration
ethtool -l ens1f0

# Set number of channels
ethtool -L ens1f0 combined 8
```

**Interrupt coalescing for throughput:**
```bash
# Reduce interrupts for high throughput
ethtool -C ens1f0 rx-usecs 100 tx-usecs 100

# For low latency (more interrupts)
ethtool -C ens1f0 rx-usecs 0 tx-usecs 0
```

## Storage Layer Optimizations

### I/O Scheduler Tuning

#### For SCSI/iSCSI Devices

**Recommended: mq-deadline or none**

```bash
# Check current scheduler
cat /sys/block/sda/queue/scheduler

# Set to mq-deadline (good for mixed workloads)
echo mq-deadline > /sys/block/sda/queue/scheduler

# Or set to none (lowest latency)
echo none > /sys/block/sda/queue/scheduler
```

**Why:** Modern storage arrays handle I/O scheduling internally; kernel scheduler adds latency.

**Make persistent:**
```bash
# Create udev rule: /etc/udev/rules.d/60-iosched.rules
ACTION=="add|change", KERNEL=="sd[a-z]", ATTR{queue/scheduler}="mq-deadline"
```

### Queue Depth Tuning

```bash
# Check current queue depth
cat /sys/block/sda/queue/nr_requests

# Increase to 256 (default is often 64 or 128)
echo 256 > /sys/block/sda/queue/nr_requests
```

### Read-Ahead Configuration

```bash
# Check current read-ahead
blockdev --getra /dev/sda

# Set read-ahead (in 512-byte sectors)
# 16384 = 8MB read-ahead (good for sequential workloads)
blockdev --setra 16384 /dev/sda
```

## iSCSI-Specific Tuning

### iSCSI Session Parameters

**Optimize session settings in /etc/iscsi/iscsid.conf:**
```bash
# Faster failover
node.session.timeo.replacement_timeout = 20

# Larger MaxRecvDataSegmentLength (up to 16MB)
node.conn[0].iscsi.MaxRecvDataSegmentLength = 262144

# Enable immediate data (reduces latency)
node.session.iscsi.ImmediateData = Yes
node.session.iscsi.FirstBurstLength = 262144
node.session.iscsi.MaxBurstLength = 16776192
```

### Multipath Performance

**Configure for throughput in /etc/multipath.conf:**
```bash
defaults {
    path_grouping_policy    multibus     # Use all paths simultaneously
    path_selector           "round-robin 0"
    failback                immediate
    no_path_retry           queue
}
```

## Monitoring Performance

**Real-time I/O monitoring:**
```bash
# Per-device statistics
iostat -xz 1

# Watch key metrics:
# - await: Average wait time (ms) - should be <20ms for iSCSI
# - %util: Utilization - sustained >80% may indicate bottleneck
# - r/s, w/s: IOPS
# - rkB/s, wkB/s: Throughput
```

**iSCSI session statistics:**
```bash
# Check session parameters
iscsiadm -m session -P 3 | grep -E "Header|Data|Burst"
```

