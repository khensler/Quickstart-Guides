Add storage interfaces to trusted zone (recommended for dedicated storage networks):

```bash
# Check if firewalld is running (skip if not installed, e.g., minimal/cloud images)
if systemctl is-active --quiet firewalld; then
    sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_1>
    sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_2>
    sudo firewall-cmd --reload
else
    echo "firewalld not running - skipping firewall configuration"
fi
```

