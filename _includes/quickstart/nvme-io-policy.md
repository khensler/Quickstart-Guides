```bash
# Create udev rule for queue-depth IO policy
sudo tee /etc/udev/rules.d/99-nvme-iopolicy.rules > /dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="nvme-subsystem", ATTR{iopolicy}="queue-depth"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

