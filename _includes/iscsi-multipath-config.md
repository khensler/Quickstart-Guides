> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## iSCSI Multipath Configuration

### Why Multipath for iSCSI?

Multipath provides critical benefits for iSCSI storage:

1. **High Availability**: Automatic failover if a path fails
   - *Why*: Network or HBA failures don't cause storage outage
2. **Load Balancing**: Distribute I/O across multiple paths
   - *Why*: Better performance and bandwidth utilization
3. **No Single Point of Failure**: Continue operating even if NICs, switches, or storage controllers fail
   - *Why*: Critical for production environments requiring high uptime
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

# Add device-specific settings for your storage array
# Consult your storage vendor documentation for recommended values
#devices {
#    device {
#        vendor "VENDOR"
#        product "PRODUCT"
#        path_selector "service-time 0"
#        path_grouping_policy "group_by_prio"
#        prio "alua"
#        failback "immediate"
#        path_checker "tur"
#        fast_io_fail_tmo 10
#        dev_loss_tmo 60
#        no_path_retry 0
#        hardware_handler "1 alua"
#        rr_min_io_rq 1
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

**Example output (with recommended `no_path_retry 0` configuration):**
```
mpatha (360014380116e6d6e00000000000000001) dm-0 VENDOR,PRODUCT
size=1.0T features='0' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| |- 3:0:0:1 sdb 8:16 active ready running
| `- 4:0:0:1 sdc 8:32 active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  |- 5:0:0:1 sdd 8:48 active ready running
  `- 6:0:0:1 sde 8:64 active ready running
```

> **Note:** When `no_path_retry 0` is configured, the `features` field shows `'0'` (no features) rather than `'1 queue_if_no_path'`. This is the recommended configuration to avoid APD (All Paths Down) hangs. See the APD section below for details.

---

## Understanding APD (All Paths Down) Events

### What is an APD Event?

An **APD (All Paths Down)** event occurs when all paths to a storage device become unavailable simultaneously. This is similar to the **Permanent Device Loss (PDL)** condition in VMware ESXi environments.

**Common causes of APD events:**
- Storage array maintenance or reboot
- Network switch failure or maintenance
- Complete loss of storage network connectivity
- Storage controller failover taking longer than expected
- Fabric-wide issues in SAN environments

### The queue_if_no_path Problem

**Issue:**
When a multipath device is configured with `features "1 queue_if_no_path"`, any process that issues I/O will **hang indefinitely** until one or more paths are restored. This can cause:
- Application timeouts
- System unresponsiveness
- Inability to gracefully shut down
- Hung processes that cannot be killed

**Why this happens:**
The `queue_if_no_path` feature tells the device mapper to queue I/O requests when all paths are down, rather than returning an error. While this prevents data loss during brief outages, it can cause severe problems during extended outages.

### Recommended Solution: no_path_retry

**Best practice:** Use `no_path_retry` instead of `queue_if_no_path`

```bash
# /etc/multipath.conf
devices {
    device {
        vendor "VENDOR"
        product "PRODUCT"
        # ... other settings ...
        no_path_retry 0        # Fail immediately when all paths are down
        # OR
        no_path_retry 5        # Retry 5 times before failing
        # OR
        no_path_retry queue    # Queue indefinitely (same as queue_if_no_path)
    }
}
```

**Recommended values:**
- `no_path_retry 0` - **Recommended for most environments**
  - Fails immediately when all paths are down
  - Prevents hung I/O and system hangs
  - Applications receive I/O errors and can handle them appropriately

- `no_path_retry 5` - For environments with brief, transient failures
  - Retries 5 times before failing
  - Provides some tolerance for momentary path loss
  - Still prevents indefinite hangs

- `no_path_retry queue` - **Not recommended**
  - Queues I/O indefinitely (same as queue_if_no_path)
  - Can cause system hangs during APD events

**Important:** The `no_path_retry` parameter **overrides** the `features "1 queue_if_no_path"` option, even if `queue_if_no_path` is set in the devices section and `no_path_retry` is set in the defaults section.

### Comparison to VMware ESXi APD Handling

**VMware ESXi APD behavior:**
- ESXi detects APD conditions and can take automated actions
- Default APD timeout: 140 seconds
- After timeout, VMs can be killed or restarted on other hosts
- Provides `disk.terminateVMOnPDLDefault` setting for PDL events

**Linux multipath APD behavior:**
- No automatic VM/application termination
- Behavior controlled by `no_path_retry` setting
- Applications must handle I/O errors appropriately
- System administrator must manually intervene during extended outages

**Key difference:** ESXi has built-in APD detection and recovery mechanisms, while Linux relies on proper multipath configuration and application-level error handling.

### Emergency Recovery from APD Events

If you're experiencing an APD event and need to change the policy at runtime:

**Change from queue_if_no_path to fail_if_no_path:**
```bash
# For a specific multipath device (e.g., mpatha)
dmsetup message mpatha 0 "fail_if_no_path"

# Verify the change
multipath -ll mpatha
```

**Important notes:**
- You must specify the multipath device name (e.g., `mpatha`), not the underlying path device
- This change is **temporary** and will be lost on reboot
- Update `/etc/multipath.conf` to make the change permanent

**To restore queue_if_no_path (if needed):**
```bash
dmsetup message mpatha 0 "queue_if_no_path"
```

### Monitoring for APD Events

**Check for failed paths:**
```bash
# View multipath status
multipath -ll

# Look for all paths in "failed" or "faulty" state
multipath -ll | grep -i "failed\|faulty"

# Check for devices with no active paths
multipath -ll | grep -A 10 "status=enabled" | grep -B 5 "0 active"
```

**Monitor system logs:**
```bash
# Check for multipath errors
journalctl -u multipathd -f

# Check for I/O errors
dmesg | grep -i "error\|fail" | grep -i "sd\|dm"

# Check for hung tasks
dmesg | grep -i "hung task"
```

### Best Practices for APD Prevention and Recovery

1. **Use no_path_retry 0 for production systems**
   - Prevents system hangs
   - Allows applications to handle errors gracefully
   - Enables faster detection and recovery

2. **Implement application-level retry logic**
   - Applications should handle I/O errors
   - Implement exponential backoff for retries
   - Log errors for monitoring and alerting

3. **Set appropriate timeout values**
   - `fast_io_fail_tmo 10` - Quick detection of path failures
   - `dev_loss_tmo 60` - Reasonable time before removing device
   - Balance between false positives and quick recovery

4. **Monitor multipath health proactively**
   - Set up alerts for path failures
   - Monitor path count and status
   - Track I/O errors and timeouts

5. **Test APD scenarios in lab**
   - Simulate complete path loss
   - Verify application behavior
   - Test recovery procedures
   - Document recovery time objectives (RTO)

6. **Plan for storage maintenance**
   - Migrate workloads before maintenance
   - Use storage array non-disruptive upgrades when available
   - Schedule maintenance during low-activity periods
   - Have rollback procedures ready

### APD Event Recovery Checklist

When experiencing an APD event:

1. **Identify the scope**
   ```bash
   multipath -ll | grep -i "failed\|faulty"
   ```

2. **Check storage array status**
   - Verify array is online and accessible
   - Check for controller failovers
   - Review array logs for errors

3. **Check network connectivity**
   ```bash
   ping <storage_portal_ip>
   nc -zv <storage_portal_ip> 3260  # iSCSI
   ```

4. **If paths won't recover, change policy**
   ```bash
   dmsetup message mpatha 0 "fail_if_no_path"
   ```

5. **Restart affected applications**
   - Stop applications gracefully if possible
   - Clear any hung I/O
   - Restart applications once paths are restored

6. **Restore paths**
   - Fix underlying network/storage issues
   - Verify paths come back online
   - Monitor for stability

7. **Update configuration to prevent recurrence**
   ```bash
   # Edit /etc/multipath.conf
   # Set no_path_retry 0
   systemctl restart multipathd
   ```

