```bash
# Check multipath is enabled
cat /sys/module/nvme_core/parameters/multipath  # Should show: Y

# Check all paths are live
sudo nvme list-subsys

# Check IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy  # Should show: queue-depth

# Verify block devices are visible
lsblk | grep nvme

# Verify storage (after LVM/filesystem creation)
df -h | grep nvme
```

**Verify Persistent Connections (recommended):**

```bash
# Reboot to confirm connections re-establish automatically
sudo reboot

# After reboot, verify all paths reconnected
sudo nvme list-subsys  # All paths should show "live"
```

