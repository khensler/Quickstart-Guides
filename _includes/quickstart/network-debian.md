Configure dedicated storage interfaces using Netplan (Ubuntu/Debian 11+):

```bash
sudo tee /etc/netplan/50-storage.yaml > /dev/null <<EOF
network:
  version: 2
  renderer: networkd
  ethernets:
    <INTERFACE_NAME_1>:
      addresses:
        - <HOST_IP_1>/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
    <INTERFACE_NAME_2>:
      addresses:
        - <HOST_IP_2>/24
      mtu: 9000
      dhcp4: no
      dhcp6: no
EOF

sudo netplan apply
ip addr show
```

