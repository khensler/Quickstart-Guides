```bash
# Check multipath is enabled
cat /sys/module/nvme_core/parameters/multipath  # Should show: Y

# Check all paths
sudo nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy  # Should show: queue-depth

# Verify storage
df -h | grep nvme
```

