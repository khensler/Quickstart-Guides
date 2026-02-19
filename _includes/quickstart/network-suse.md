Configure dedicated storage interfaces using Wicked (SUSE default):

```bash
# First storage interface
sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_1> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_1>/24'
MTU='9000'
NAME='Storage Network 1'
EOF

# Second storage interface
sudo tee /etc/sysconfig/network/ifcfg-<INTERFACE_NAME_2> > /dev/null <<EOF
BOOTPROTO='static'
STARTMODE='auto'
IPADDR='<HOST_IP_2>/24'
MTU='9000'
NAME='Storage Network 2'
EOF

# Apply configuration
sudo wicked ifreload all
ip addr show
```

