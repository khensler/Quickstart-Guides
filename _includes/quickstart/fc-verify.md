```bash
# Check HBA port state (all should be Online)
cat /sys/class/fc_host/host*/port_state

# Check multipath paths and ALUA priority groups
sudo multipath -ll

# Verify storage device is visible
lsscsi | grep PURE

# Verify filesystem is mounted (if applicable)
df -h | grep fc-storage
```

