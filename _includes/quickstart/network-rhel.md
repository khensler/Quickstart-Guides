```bash
# First storage interface
sudo nmcli connection add type ethernet \
    con-name storage-1 \
    ifname <INTERFACE_NAME_1> \
    ipv4.method manual \
    ipv4.addresses <HOST_IP_1>/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Second storage interface
sudo nmcli connection add type ethernet \
    con-name storage-2 \
    ifname <INTERFACE_NAME_2> \
    ipv4.method manual \
    ipv4.addresses <HOST_IP_2>/24 \
    ipv4.never-default yes \
    802-3-ethernet.mtu 9000 \
    connection.autoconnect yes

# Activate
sudo nmcli connection up storage-1
sudo nmcli connection up storage-2
```

