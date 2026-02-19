## Step 2: Enable Native NVMe Multipath

```bash
# Enable multipath BEFORE connecting (requires reboot to take effect)
echo 'options nvme_core multipath=Y' | sudo tee /etc/modprobe.d/nvme-tcp.conf
sudo reboot
```

