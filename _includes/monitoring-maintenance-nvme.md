> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Monitoring & Maintenance

### Daily Monitoring Tasks

#### Path Health Monitoring

**Check NVMe native multipath status:**
```bash
# View all NVMe subsystems and paths
nvme list-subsys

# Check for non-live paths
nvme list-subsys | grep -v "live"

# Count active paths per subsystem
nvme list-subsys | grep -c "live"
```

**Expected output:**
- All paths should show `live` state
- No `connecting`, `deleting`, or failed paths
- Path count matches expected (e.g., 8 paths for 2 NICs × 4 portals)

**Alert conditions:**
- Any path shows non-live status
- Path count is less than expected
- All paths to a single controller are down

#### Connection Status

**NVMe-TCP connections:**
```bash
# List all NVMe connections
nvme list-subsys

# Check connection state
nvme list | grep -E "live|connecting|dead"

# Count active connections
nvme list-subsys | grep -c "live"
```

**Expected output:**
- All connections show `live` state
- Connection count matches expected configuration
- No `connecting` or failed states

#### Performance Metrics

**I/O latency:**
```bash
# Monitor I/O latency with iostat
iostat -x 1 5

# Key metrics to watch:
# - await: Average I/O wait time (should be <1ms for NVMe-TCP)
# - %util: Device utilization (sustained >80% may indicate bottleneck)
```

**Network throughput:**
```bash
# Monitor network I/O
iftop -i <storage_interface>

# Or use nload
nload <storage_interface>
```

**Disk I/O:**
```bash
# Real-time I/O monitoring
iotop -o

# Per-device statistics
iostat -dx 1
```

### Weekly Monitoring Tasks

#### Storage Array Health

**NVMe SMART data:**
```bash
# Check NVMe device health
nvme smart-log /dev/nvme0n1

# Key metrics:
# - critical_warning: Should be 0
# - temperature: Should be within normal range
# - available_spare: Should be >10%
# - percentage_used: Monitor for wear
```

**NVMe path statistics:**
```bash
# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy

# Check ANA state (if supported)
nvme list-subsys -o json | grep -E "state|ana"
```

#### Log Review

**Check system logs for storage errors:**
```bash
# NVMe errors
journalctl -u nvmf-autoconnect -p err --since "7 days ago"

# NVMe kernel messages
dmesg -T | grep -i "nvme" | grep -i "error\|fail\|timeout"

# Check for connection issues
journalctl --since "7 days ago" | grep -i "nvme.*connect\|nvme.*disconnect"
```

**Common errors to investigate:**
- I/O errors or timeouts
- Path failures
- Connection drops
- Controller resets

#### Performance Trending

**Collect baseline metrics:**
```bash
# Create performance snapshot
{
    echo "=== Date: $(date) ==="
    echo "=== NVMe Subsystems ==="
    nvme list-subsys
    echo "=== I/O Statistics ==="
    iostat -x
    echo "=== Network Statistics ==="
    ip -s link show
    echo "=== NVMe List ==="
    nvme list
    echo "=== IO Policy ==="
    cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
} > /var/log/storage-snapshot-$(date +%Y%m%d).log
```

**Analyze trends:**
- Compare weekly snapshots
- Look for degrading performance
- Identify capacity trends
- Plan for growth

### Monthly Maintenance Tasks

#### Firmware Updates

**Check for updates:**
- Storage array firmware
- NIC firmware
- Switch firmware

**Update procedure:**
1. Review release notes
2. Test in non-production environment
3. Schedule maintenance window
4. Backup configurations
5. Apply updates
6. Verify functionality
7. Monitor for issues

**Best practices:**
- Never update all components simultaneously
- Update one component type at a time
- Allow 1-2 weeks between updates to identify issues
- Keep previous firmware versions for rollback

#### Configuration Backup

**Backup critical configurations:**
```bash
# Network configuration
cp -a /etc/NetworkManager/system-connections/ /backup/network-$(date +%Y%m%d)

# NVMe configuration
cp -a /etc/nvme/hostnqn /backup/hostnqn-$(date +%Y%m%d)
cp -a /etc/nvme/discovery.conf /backup/discovery.conf-$(date +%Y%m%d)
cp -a /etc/modprobe.d/nvme*.conf /backup/nvme-modprobe-$(date +%Y%m%d)
cp -a /etc/udev/rules.d/*nvme*.rules /backup/nvme-udev-$(date +%Y%m%d)
```

**Automate backups:**
```bash
# Create backup script: /usr/local/bin/backup-nvme-config.sh
#!/bin/bash
BACKUP_DIR="/backup/nvme-configs"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR/$DATE
cp -a /etc/NetworkManager/system-connections/ $BACKUP_DIR/$DATE/
cp -a /etc/nvme/ $BACKUP_DIR/$DATE/
cp -a /etc/modprobe.d/nvme*.conf $BACKUP_DIR/$DATE/ 2>/dev/null
cp -a /etc/udev/rules.d/*nvme*.rules $BACKUP_DIR/$DATE/ 2>/dev/null

# Keep only last 90 days
find $BACKUP_DIR -type d -mtime +90 -exec rm -rf {} \;
```

**Schedule with cron:**
```bash
# Add to crontab
0 2 1 * * /usr/local/bin/backup-nvme-config.sh
```

### Quarterly Maintenance Tasks

#### Failover Testing

**Test NIC failover:**
```bash
# 1. Bring down a storage NIC
ip link set <interface> down

# 2. Verify connections fail over
nvme list-subsys

# 3. Verify I/O continues
iostat -x 1 5

# 4. Bring NIC back up
ip link set <interface> up

# 5. Verify connections restore
nvme list-subsys
```

**Document results:**
- Failover time
- Any errors or warnings
- Recovery time
- Lessons learned

#### Capacity Planning

**Review storage usage:**
```bash
# Check LVM usage
pvs
vgs
lvs

# Check filesystem usage
df -h

# Trend analysis
# Compare with previous months
# Project growth rate
# Plan for expansion
```

**Recommendations:**
- Maintain 20% free space minimum
- Plan expansion when 70% full
- Review growth trends quarterly
- Budget for capacity increases

### Maintenance Checklist

**Daily:**
- [ ] Check NVMe path health: `nvme list-subsys`
- [ ] Check IO policy: `cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy`
- [ ] Review performance metrics
- [ ] Check for alerts/errors

**Weekly:**
- [ ] Review NVMe SMART data
- [ ] Analyze system logs
- [ ] Collect performance baselines
- [ ] Verify backup completion

**Monthly:**
- [ ] Check for firmware updates
- [ ] Backup configurations
- [ ] Review security patches
- [ ] Update documentation

**Quarterly:**
- [ ] Test failover procedures
- [ ] Capacity planning review
- [ ] Security audit
- [ ] Disaster recovery test
- [ ] Update runbooks

