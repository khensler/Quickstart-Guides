```bash
# Check mount options
mount | grep nfs

# Verify nconnect is active
cat /proc/fs/nfsfs/servers

# Test read/write
echo "NFS test" | sudo tee /mnt/pure-nfs/test.txt
cat /mnt/pure-nfs/test.txt
sudo rm /mnt/pure-nfs/test.txt
```

