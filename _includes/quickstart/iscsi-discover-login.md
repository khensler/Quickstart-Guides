```bash
# Discover targets
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:3260
sudo iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:3260

# Login via each interface to each portal
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface0 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_1>:3260 -I iface1 --login
sudo iscsiadm -m node -T <TARGET_IQN> -p <PORTAL_IP_2>:3260 -I iface1 --login

# Set automatic login
sudo iscsiadm -m node -T <TARGET_IQN> --op=update -n node.startup -v automatic

# Verify sessions
sudo iscsiadm -m session
```

