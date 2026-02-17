---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

## iSCSI Multipath Configuration

### Why Multipath for iSCSI?

Multipath provides critical benefits for iSCSI storage:

1. **High Availability**: Automatic failover if a path fails
   - *Why*: Network or HBA failures don't cause storage outage
2. **Load Balancing**: Distribute I/O across multiple paths
   - *Why*: Better performance and bandwidth utilization
3. **No Single Point of Failure**: Continue operating even if NICs, switches, or storage controllers fail
   - *Why*: Critical for production environments requiring 99.99%+ uptime
4. **Zero Downtime Maintenance**: Perform maintenance on network components without storage outage
   - *Why*: Enables rolling upgrades and maintenance windows

### Path Redundancy Calculation

With **N** host interfaces and **M** storage portals, you get **N × M** total paths.

**Example:**
- 2 host NICs × 2 storage portals = **4 paths**
- 4 host NICs × 4 storage portals = **16 paths**

**Recommended minimum:** 4 paths (2×2) for production environments

### dm-multipath Configuration

#### Basic Configuration Structure

```bash
# /etc/multipath.conf
defaults {
    user_friendly_names yes
    find_multipaths no
    enable_foreign "^$"
}

blacklist {
    # Exclude local disks and system devices
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^hd[a-z]"
    devnode "^cciss.*"
}

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
```

#### Key Parameters Explained

**path_selector "service-time 0"**
- *What*: Selects path with lowest estimated service time
- *Why*: Automatically balances load based on actual path performance
- *Alternative*: "round-robin 0" for simple round-robin

**path_grouping_policy "group_by_prio"**
- *What*: Groups paths by priority (ALUA state)
- *Why*: Ensures active/optimized paths are used first
- *Result*: Better performance by using optimal paths

**prio "alua"**
- *What*: Uses ALUA (Asymmetric Logical Unit Access) for path priority
- *Why*: Storage array indicates which paths are optimized
- *Result*: Automatic selection of best paths

**failback "immediate"**
- *What*: Immediately fail back to preferred path when available
- *Why*: Ensures optimal path is always used
- *Alternative*: "manual" or time-based failback

**fast_io_fail_tmo 10**
- *What*: Timeout for I/O on failed path (10 seconds)
- *Why*: Quick detection and failover on path failure
- *Impact*: Reduces application wait time during failures

**dev_loss_tmo 60**
- *What*: Time before device is removed (60 seconds)
- *Why*: Allows time for path recovery without removing device
- *Balance*: Long enough for transient issues, short enough for real failures

**no_path_retry 0**
- *What*: Don't queue I/O when all paths are down
- *Why*: Fail fast rather than hanging applications
- *Alternative*: Set to number for retry attempts, or "queue" to wait indefinitely

### Path Selection Policies

**service-time** (Recommended for most workloads)
- Selects path with lowest service time
- Automatically adapts to path performance
- Best for mixed workloads

**queue-length**
- Selects path with fewest outstanding I/Os
- Good for high-throughput sequential workloads
- May not account for path speed differences

**round-robin**
- Simple rotation through all paths
- Predictable but doesn't adapt to performance
- Good for testing or homogeneous paths

### Interface Binding

**Why bind iSCSI to specific interfaces:**
- Ensures multipath uses all configured paths
- Prevents all sessions from using single interface
- Enables proper load distribution
- Required for same-subnet multipath

**Configuration:**
```bash
# Create interface binding
iscsiadm -m iface -I iface-eth0 -o new
iscsiadm -m iface -I iface-eth0 -o update -n iface.net_ifacename -v eth0

iscsiadm -m iface -I iface-eth1 -o new
iscsiadm -m iface -I iface-eth1 -o update -n iface.net_ifacename -v eth1

# Login using specific interface
iscsiadm -m node -T <target_iqn> -p <portal_ip>:3260 -I iface-eth0 --login
iscsiadm -m node -T <target_iqn> -p <portal_ip>:3260 -I iface-eth1 --login
```

### Monitoring Multipath

**Check path status:**
```bash
# View all multipath devices and paths
multipath -ll

# Verbose output
multipath -v3

# Reload configuration
multipath -r
```

**Example output:**
```
mpatha (360014380116e6d6e00000000000000001) dm-0 PURE,FlashArray
size=1.0T features='1 queue_if_no_path' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| |- 3:0:0:1 sdb 8:16 active ready running
| `- 4:0:0:1 sdc 8:32 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  |- 5:0:0:1 sdd 8:48 active ready running
  `- 6:0:0:1 sde 8:64 active ready running
```

