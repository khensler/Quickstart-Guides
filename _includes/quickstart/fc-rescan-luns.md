```bash
# Option 1: rescan-scsi-bus (preferred — discovers new devices on all host bus adapters)
sudo rescan-scsi-bus.sh

# Option 2: sysfs manual rescan (if rescan-scsi-bus is unavailable)
for host in /sys/class/scsi_host/host*; do
    echo "- - -" | sudo tee "$host/scan"
done

# Verify devices appeared
lsscsi | grep PURE
# Example output:
# [6:0:0:1]  disk  PURE     FlashArray       006.  /dev/sdb

# Confirm multipath picked them up
sudo multipath -ll
```

> **If no PURE devices appear:** Verify zoning is complete, the volume is connected on the array, and HBA port state is `Online`. See [Troubleshooting](#troubleshooting) in the Best Practices guide.

