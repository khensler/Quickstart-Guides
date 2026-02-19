```bash
# Find multipath device
sudo multipath -ll
# Example: mpatha

# Create LVM
sudo pvcreate /dev/mapper/mpatha
sudo vgcreate iscsi-storage /dev/mapper/mpatha
sudo lvcreate -L 500G -n data iscsi-storage
```

