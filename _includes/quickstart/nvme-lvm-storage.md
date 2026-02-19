```bash
# Find NVMe device
sudo nvme list
# Example: /dev/nvme0n1

# Create LVM
sudo pvcreate /dev/nvme0n1
sudo vgcreate nvme-storage /dev/nvme0n1
sudo lvcreate -L 500G -n data nvme-storage
```

