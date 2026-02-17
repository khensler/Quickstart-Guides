---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

## Multipath Configuration

### Why Multipath?

Multipath provides:
1. **High Availability**: Automatic failover if a path fails
2. **Load Balancing**: Distribute I/O across multiple paths for better performance
3. **No Single Point of Failure**: Continue operating even if NICs, switches, or storage controllers fail
4. **Zero Downtime Maintenance**: Perform maintenance on network components without storage outage

### Path Redundancy Calculation

With **N** host interfaces and **M** storage portals, you get **N × M** total paths.

**Example:**
- 2 host NICs × 4 storage portals = **8 paths**
- Each path is independent and can fail without affecting others
- Minimum recommended: 4 paths (2×2 configuration)

### Multipath Path Selection Policies

Different policies optimize for different goals:

#### service-time (Recommended for Most Workloads)

**How it works:** Sends I/O to the path with the shortest estimated service time (queue depth + latency)

**Best for:**
- Mixed workloads (random + sequential)
- General purpose storage
- Active-active storage arrays

**Why recommended:**
- Automatically balances load based on actual performance
- Adapts to changing conditions
- Works well with most storage arrays

**Configuration:**
```bash
path_selector "service-time 0"
```

#### queue-length

**How it works:** Sends I/O to the path with the fewest outstanding I/O requests

**Best for:**
- High queue depth workloads
- Workloads with variable I/O sizes

**Configuration:**
```bash
path_selector "queue-length 0"
```

#### round-robin

**How it works:** Distributes I/O evenly across all paths in rotation

**Best for:**
- Sequential I/O workloads
- Maximum throughput scenarios
- Benchmarking

**Considerations:**
- Can cause out-of-order I/O delivery
- May not be optimal for random I/O

**Configuration:**
```bash
path_selector "round-robin 0"
```

### Path Grouping Policies

#### group_by_prio (Recommended)

**How it works:** Groups paths by priority (from ALUA or manual configuration)

**Best for:**
- Active-active storage arrays with ALUA
- Asymmetric storage configurations

**Why recommended:**
- Respects storage array's preferred paths
- Optimizes for storage controller affinity
- Prevents suboptimal path usage

#### multibus

**How it works:** All paths in a single group, all active

**Best for:**
- Symmetric active-active arrays
- Maximum path utilization

#### failover

**How it works:** Only one path active at a time, others are standby

**Best for:**
- Active-passive storage arrays
- Troubleshooting

### Multipath Features

#### queue_if_no_path (NOT RECOMMENDED)

**What it does:** Queue I/O if all paths fail instead of returning errors

**⚠️ NOT Recommended:** Avoid using `features "1 queue_if_no_path"` in production

**Why it's dangerous:**
- Causes I/O to hang **indefinitely** if paths don't recover
- Can make system unresponsive during storage outages
- Hung processes cannot be killed (D state)
- May cause similar issues to VMware ESXi APD (All Paths Down) events

**See also:** [APD (All Paths Down) Events](#understanding-apd-events) in iSCSI multipath configuration

#### no_path_retry (RECOMMENDED)

**What it does:** Number of times to retry I/O when all paths are down before failing

**Recommended setting:** `no_path_retry 0`

**Why:**
- **`no_path_retry 0`** - Fail immediately when all paths are down (recommended)
  - Applications receive errors and can handle them appropriately
  - Prevents hung I/O and system hangs
  - Most predictable behavior for applications

- **`no_path_retry 5-30`** - For environments with brief, transient failures
  - Provides some tolerance for momentary path loss
  - Still prevents indefinite hangs

**Important:** The `no_path_retry` parameter **overrides** the `features "1 queue_if_no_path"` option

### Path Failure Detection

#### fast_io_fail_tmo

**What it does:** Time to wait before marking a path as failed

**Recommended setting:** `fast_io_fail_tmo 5`

**Why:**
- Quick detection of failed paths (5 seconds)
- Faster failover to working paths
- Reduces I/O latency during failures

#### dev_loss_tmo

**What it does:** Time to wait before removing a failed device

**Recommended setting:** `dev_loss_tmo 30`

**Why:**
- Allows time for transient failures to recover
- Prevents device removal during brief outages
- Should be longer than fast_io_fail_tmo

### Monitoring Multipath Health

**Check path status:**
```bash
# View all multipath devices and their paths
multipath -ll

# Check for failed paths
multipath -ll | grep -E "failed|faulty"

# Count active paths per device
multipath -ll | grep -E "status=active|status=enabled"
```

**Verify path distribution:**
```bash
# Check I/O statistics per path
dmsetup status <device>

# Monitor path switching
watch -n 1 'multipath -ll'
```

**Test path failover:**
```bash
# Disable a path to test failover
echo 1 > /sys/block/<device>/device/delete

# Re-scan to restore path
echo "- - -" > /sys/class/scsi_host/host<N>/scan
```

