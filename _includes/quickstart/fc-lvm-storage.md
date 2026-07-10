```bash
# Find multipath device
sudo multipath -ll
# Example: mpatha → /dev/mapper/mpatha
# Or by WWID: /dev/mapper/3624a937...

# Create LVM
sudo pvcreate /dev/mapper/mpatha
sudo vgcreate fc-storage /dev/mapper/mpatha
sudo lvcreate -L 500G -n data fc-storage
```

