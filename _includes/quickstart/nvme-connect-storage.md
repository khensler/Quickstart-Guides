Connect each host interface to each storage portal:

```bash
# Replace values: <PORTAL_IP_X>, <SUBSYSTEM_NQN>, <INTERFACE_NAME_X>, <HOST_IP_X>
sudo nvme connect -t tcp -a <PORTAL_IP_1> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

sudo nvme connect -t tcp -a <PORTAL_IP_2> -s 4420 -n <SUBSYSTEM_NQN> \
    --host-iface=<INTERFACE_NAME_1> --host-traddr=<HOST_IP_1> \
    --ctrl-loss-tmo=1800 --reconnect-delay=10

# Repeat for all portal/interface combinations to create full mesh

# Verify connections
sudo nvme list-subsys
```

