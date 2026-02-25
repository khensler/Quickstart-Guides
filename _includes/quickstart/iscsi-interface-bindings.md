```bash
# Create and bind first interface
sudo iscsiadm -m iface -I iface0 --op=new
sudo iscsiadm -m iface -I iface0 --op=update -n iface.net_ifacename -v <INTERFACE_NAME_1>

# Create and bind second interface
sudo iscsiadm -m iface -I iface1 --op=new
sudo iscsiadm -m iface -I iface1 --op=update -n iface.net_ifacename -v <INTERFACE_NAME_2>
```

