Add storage interfaces to trusted zone (recommended for dedicated storage networks):

```bash
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_1>
sudo firewall-cmd --permanent --zone=trusted --add-interface=<INTERFACE_NAME_2>
sudo firewall-cmd --reload
```

