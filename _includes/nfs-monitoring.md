### Health Checks

```bash
# Check mount status
mount | grep nfs
df -h | grep nfs

# NFS statistics
nfsstat -c

# Check for errors
dmesg | grep -i nfs
```

### Automated Monitoring

```bash
#!/bin/bash
# /usr/local/bin/check-nfs-health.sh
MOUNT_POINT="/mnt/pure-nfs"

if ! mountpoint -q "$MOUNT_POINT"; then
    echo "ERROR: NFS not mounted"
    exit 1
fi

if ! ls "$MOUNT_POINT" > /dev/null 2>&1; then
    echo "ERROR: NFS not accessible"
    exit 1
fi

echo "OK: NFS healthy"
```

