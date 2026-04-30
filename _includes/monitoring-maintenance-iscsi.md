# Monitoring and Maintenance (iSCSI)

## Regular Health Checks

### Connection Monitoring

#### Connection Status

**iSCSI sessions:**
```bash
iscsiadm -m session
iscsiadm -m session -P 3 | grep -E "State|iSCSI Connection State"
```

#### I/O Statistics

```bash
# Real-time I/O stats
iostat -xz 1

# Per-device statistics
iostat -xz -d sda sdb 1

# Key metrics to watch:
# - await: Average I/O wait time (should be <20ms for iSCSI)
# - %util: Device utilization (sustained >80% may indicate bottleneck)
```

### Device Health

#### Multipath Status

```bash
# Show multipath topology
multipath -ll

# Show multipath status
multipathd show status

# Check individual path states
multipathd show paths
```

#### Storage Array Health

**Monitor iSCSI sessions:**
```bash
# Check session parameters
iscsiadm -m session -P 3

# Key items to check:
# - Connection state: should be "LOGGED_IN"
# - Internal iscsid Session State: should be "NO CHANGE"
```

### Log Monitoring

#### Error Detection

**Check system logs for storage errors:**
```bash
# iSCSI errors
journalctl -u iscsid -p err --since "7 days ago"

# Multipath errors
journalctl -u multipathd -p err --since "7 days ago"

# Kernel errors related to storage
dmesg -T | grep -i "iscsi\|dm-\|multipath" | grep -i "error\|fail"
```

#### Automated Monitoring Script

```bash
#!/bin/bash
# storage-monitor.sh - Quick storage health check

{
    echo "=== Storage Health Check $(date) ==="
    echo "=== iSCSI Sessions ==="
    iscsiadm -m session
    echo "=== Multipath Devices ==="
    multipath -ll
    echo "=== I/O Statistics ==="
    iostat -xz 1 1
    echo "=== Network Statistics ==="
    ip -s link show
} > /var/log/storage-snapshot-$(date +%Y%m%d).log
```

## Maintenance Procedures

### Graceful Storage Disconnection

**Before maintenance:**
```bash
# 1. Stop applications using storage
systemctl stop your-application

# 2. Unmount filesystems
umount /dev/mapper/mpatha*

# 3. Flush multipath devices
multipath -F

# 4. Logout iSCSI sessions
iscsiadm -m node -U all

# 5. Stop iSCSI service
systemctl stop iscsid
```

### Configuration Backup

**Regular backup of storage configuration:**
```bash
# Multipath configuration
cp -a /etc/multipath.conf /backup/multipath.conf-$(date +%Y%m%d)

# iSCSI configuration
cp -a /etc/iscsi/ /backup/iscsi-$(date +%Y%m%d)
```

**Automated backup script:**
```bash
#!/bin/bash
# storage-config-backup.sh

BACKUP_DIR="/backup/storage-config"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR/$DATE

cp -a /etc/network/interfaces $BACKUP_DIR/$DATE/
cp -a /etc/multipath.conf $BACKUP_DIR/$DATE/
cp -a /etc/iscsi/ $BACKUP_DIR/$DATE/

# Create tarball
tar -czf $BACKUP_DIR/storage-config-$DATE.tar.gz $BACKUP_DIR/$DATE/

# Keep last 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR/storage-config-$DATE.tar.gz"
```

### Firmware/Driver Updates

**Planning checklist:**
1. Schedule maintenance window
2. Backup current configuration
3. Migrate VMs if applicable
4. Update drivers/firmware
5. Verify connectivity
6. Test failover

**Verification after updates:**
```bash
# 1. Check iSCSI sessions
iscsiadm -m session

# 2. Verify multipath
multipath -ll

# 3. Check I/O performance
fio --name=test --rw=randread --size=100M --runtime=10

# 4. Test failover (disconnect one path)
# Verify I/O continues without interruption
```

