---
layout: default
title: Performance Tuning
---

> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Performance Optimization

### CPU and Interrupt Tuning

#### CPU Isolation for Storage I/O

**Why:** Dedicate CPU cores to storage I/O processing to reduce latency and improve consistency

**Configuration:**
```bash
# Edit /etc/default/grub
GRUB_CMDLINE_LINUX="isolcpus=2,3,10,11"

# Update grub
update-grub
reboot
```

**Best Practice:**
- Isolate 2-4 cores per storage NIC
- Use cores on the same NUMA node as the NIC
- Leave enough cores for VM workloads

#### IRQ Affinity

**Why:** Pin NIC interrupts to specific CPUs to reduce cache thrashing and improve performance

**Find NIC IRQs:**
```bash
# Find IRQ numbers for your storage NIC
grep <interface_name> /proc/interrupts
```

**Set IRQ affinity:**
```bash
# Pin IRQ to specific CPU (CPU 2 = bitmask 0x4)
echo 4 > /proc/irq/<IRQ_NUMBER>/smp_affinity
```

**Automated script:**
```bash
#!/bin/bash
# set-irq-affinity.sh
INTERFACE="ens1f0"
CPU_START=2

IRQ_LIST=$(grep $INTERFACE /proc/interrupts | awk '{print $1}' | sed 's/://')
CPU=$CPU_START

for IRQ in $IRQ_LIST; do
    MASK=$(printf "%x" $((1 << $CPU)))
    echo $MASK > /proc/irq/$IRQ/smp_affinity
    echo "IRQ $IRQ -> CPU $CPU (mask: $MASK)"
    CPU=$((CPU + 1))
done
```

### Memory and I/O Tuning

#### Kernel Parameters

**Edit `/etc/sysctl.conf` or create `/etc/sysctl.d/99-storage-tuning.conf`:**

```bash
# Increase network buffer sizes
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.core.rmem_default = 16777216
net.core.wmem_default = 16777216

# Increase TCP buffer sizes
net.ipv4.tcp_rmem = 4096 87380 67108864
net.ipv4.tcp_wmem = 4096 65536 67108864

# Increase maximum number of queued connections
net.core.netdev_max_backlog = 30000

# Increase socket listen backlog
net.core.somaxconn = 4096

# Enable TCP window scaling
net.ipv4.tcp_window_scaling = 1

# Disable TCP timestamps (reduces overhead)
net.ipv4.tcp_timestamps = 0

# Enable TCP selective acknowledgments
net.ipv4.tcp_sack = 1

# Increase ARP cache size
net.ipv4.neigh.default.gc_thresh1 = 4096
net.ipv4.neigh.default.gc_thresh2 = 8192
net.ipv4.neigh.default.gc_thresh3 = 16384

# VM tuning for storage workloads
vm.dirty_ratio = 10
vm.dirty_background_ratio = 5
vm.swappiness = 10
```

**Apply changes:**
```bash
sysctl -p /etc/sysctl.d/99-storage-tuning.conf
```

**Why these settings:**
- **Buffer sizes**: Accommodate high-bandwidth storage traffic
- **Backlog**: Handle burst traffic without drops
- **Window scaling**: Enable large TCP windows for high-bandwidth×delay networks
- **Timestamps**: Reduce per-packet overhead (trade-off: no RTT measurement)
- **ARP cache**: Prevent ARP table overflow in large storage networks
- **VM dirty ratios**: Prevent large amounts of dirty data in cache, improving write consistency

### I/O Scheduler Tuning

#### For NVMe Devices

**Recommended: none (no scheduler)**

```bash
# Check current scheduler
cat /sys/block/nvme0n1/queue/scheduler

# Set to none
echo none > /sys/block/nvme0n1/queue/scheduler
```

**Why:** NVMe devices have their own internal scheduling; kernel scheduler adds unnecessary overhead

**Make persistent:**
```bash
# Create udev rule: /etc/udev/rules.d/60-iosched.rules
ACTION=="add|change", KERNEL=="nvme[0-9]n[0-9]", ATTR{queue/scheduler}="none"
```

#### Queue Depth

**Increase queue depth for better parallelism:**

```bash
# Check current queue depth
cat /sys/block/nvme0n1/queue/nr_requests

# Increase to 1024 (default is often 256)
echo 1024 > /sys/block/nvme0n1/queue/nr_requests
```

**Why:** Higher queue depth allows more concurrent I/O operations, improving throughput

### NIC Tuning

#### Offload Features

**Enable hardware offloads to reduce CPU usage:**

```bash
# Enable all offloads
ethtool -K <interface> tso on gso on gro on lro on

# Verify
ethtool -k <interface>
```

**Offload types:**
- **TSO (TCP Segmentation Offload)**: NIC handles TCP segmentation
- **GSO (Generic Segmentation Offload)**: Kernel-level segmentation
- **GRO (Generic Receive Offload)**: Aggregate received packets
- **LRO (Large Receive Offload)**: Hardware packet aggregation

**Why:** Reduces CPU overhead for packet processing, freeing CPU for other tasks

#### Ring Buffers

**Increase ring buffer sizes:**

```bash
# Check current settings
ethtool -g <interface>

# Set to maximum
ethtool -G <interface> rx 4096 tx 4096
```

**Why:** Larger buffers reduce packet drops during traffic bursts

### Monitoring Performance

**Real-time I/O monitoring:**
```bash
# Monitor disk I/O
iostat -x 1

# Monitor network I/O
iftop -i <interface>

# Monitor multipath I/O distribution
watch -n 1 'dmsetup status'
```

**Latency monitoring:**
```bash
# Monitor NVMe latency
nvme smart-log /dev/nvme0n1 | grep -i latency

# Monitor I/O latency with ioping
ioping -c 10 /dev/mapper/<device>
```

**Throughput testing:**
```bash
# Test sequential read
fio --name=seqread --rw=read --bs=1M --size=10G --filename=/dev/mapper/<device>

# Test sequential write
fio --name=seqwrite --rw=write --bs=1M --size=10G --filename=/dev/mapper/<device>

# Test random read IOPS
fio --name=randread --rw=randread --bs=4k --size=10G --filename=/dev/mapper/<device>
```

