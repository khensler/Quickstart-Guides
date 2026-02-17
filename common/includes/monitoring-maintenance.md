---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

## Monitoring & Maintenance

### Daily Monitoring Tasks

#### Path Health Monitoring

**Check multipath status:**
```bash
# View all paths and their status
multipath -ll

# Check for failed paths
multipath -ll | grep -E "failed|faulty|offline"

# Count active paths per device
multipath -ll | awk '/status=active/ {count++} END {print "Active paths:", count}'
```

**Expected output:**
- All paths should show `status=active` or `status=enabled`
- No `failed`, `faulty`, or `offline` paths
- Path count matches expected (e.g., 8 paths for 2×4 configuration)

**Alert conditions:**
- Any path shows failed/faulty status
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

**iSCSI sessions:**
```bash
# List all active sessions
iscsiadm -m session

# Check session state
iscsiadm -m session -P 3 | grep -E "State|iSCSI Connection State"
```

**Expected output:**
- All connections show `live` or `logged in` state
- Connection count matches expected configuration
- No `dead`, `connecting`, or `failed` states

#### Performance Metrics

**I/O latency:**
```bash
# Monitor I/O latency with iostat
iostat -x 1 5

# Key metrics to watch:
# - await: Average I/O wait time (should be <10ms for NVMe)
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

**Multipath statistics:**
```bash
# Check I/O distribution across paths
dmsetup status

# Verify load balancing
multipath -ll | grep -A 10 "policy="
```

#### Log Review

**Check system logs for storage errors:**
```bash
# NVMe errors
journalctl -u nvme -p err --since "7 days ago"

# iSCSI errors
journalctl -u iscsid -p err --since "7 days ago"

# Multipath errors
journalctl | grep -i "multipath\|dm-" | grep -i "error\|fail" --since "7 days ago"

# Kernel errors related to storage
dmesg -T | grep -i "nvme\|iscsi\|dm-\|multipath" | grep -i "error\|fail"
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
    echo "=== Multipath Status ==="
    multipath -ll
    echo "=== I/O Statistics ==="
    iostat -x
    echo "=== Network Statistics ==="
    ip -s link show
    echo "=== NVMe List ==="
    nvme list
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
- HBA/CNA firmware (if applicable)

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
cp -a /etc/network/interfaces /backup/network-interfaces-$(date +%Y%m%d)

# Multipath configuration
cp -a /etc/multipath.conf /backup/multipath.conf-$(date +%Y%m%d)

# NVMe configuration
cp -a /etc/nvme/hostnqn /backup/hostnqn-$(date +%Y%m%d)
cp -a /etc/nvme/discovery.conf /backup/discovery.conf-$(date +%Y%m%d)

# iSCSI configuration
cp -a /etc/iscsi/ /backup/iscsi-$(date +%Y%m%d)

# Storage configuration
cp -a /etc/pve/storage.cfg /backup/storage.cfg-$(date +%Y%m%d)
```

**Automate backups:**
```bash
# Create backup script: /usr/local/bin/backup-storage-config.sh
#!/bin/bash
BACKUP_DIR="/backup/storage-configs"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR/$DATE
cp -a /etc/network/interfaces $BACKUP_DIR/$DATE/
cp -a /etc/multipath.conf $BACKUP_DIR/$DATE/
cp -a /etc/nvme/ $BACKUP_DIR/$DATE/
cp -a /etc/iscsi/ $BACKUP_DIR/$DATE/
cp -a /etc/pve/storage.cfg $BACKUP_DIR/$DATE/

# Keep only last 90 days
find $BACKUP_DIR -type d -mtime +90 -exec rm -rf {} \;
```

**Schedule with cron:**
```bash
# Add to crontab
0 2 1 * * /usr/local/bin/backup-storage-config.sh
```

### Quarterly Maintenance Tasks

#### Failover Testing

**Test path failover:**
```bash
# 1. Identify a path to test
multipath -ll

# 2. Disable the path
echo 1 > /sys/block/<device>/device/delete

# 3. Verify I/O continues on other paths
multipath -ll
iostat -x 1 5

# 4. Re-enable the path
echo "- - -" > /sys/class/scsi_host/host<N>/scan

# 5. Verify path is restored
multipath -ll
```

**Test NIC failover:**
```bash
# 1. Bring down a storage NIC
ip link set <interface> down

# 2. Verify connections fail over
nvme list-subsys  # or iscsiadm -m session

# 3. Verify I/O continues
iostat -x 1 5

# 4. Bring NIC back up
ip link set <interface> up

# 5. Verify connections restore
nvme list-subsys  # or iscsiadm -m session
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
- [ ] Monitor path health
- [ ] Check connection status
- [ ] Review performance metrics
- [ ] Check for alerts/errors

**Weekly:**
- [ ] Review storage array health
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

