## Quick Reference

**Discover subsystems:**
```bash
sudo nvme discover -t tcp -a <portal_ip> -s 8009
```

**Connect to subsystem:**
```bash
sudo nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn>
```

**Check connections:**
```bash
sudo nvme list-subsys
```

**Check multipath (native NVMe):**
```bash
sudo nvme list-subsys
# Look for multiple paths per nvme device
```

