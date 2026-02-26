**Option A: Connect-all (simplest method)**

Discovers and connects to all available subsystems from a single portal:

```bash
# Replace <PORTAL_IP_1> with any storage portal IP
sudo nvme connect-all -t tcp -a <PORTAL_IP_1> -s 4420

# Verify connections
sudo nvme list-subsys
```

**Option B: Individual connections (for specific interface binding)**

Use when you need to bind connections to specific host interfaces:

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

