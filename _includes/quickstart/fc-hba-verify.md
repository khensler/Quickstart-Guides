```bash
# Check which FC HBA drivers are loaded
lsmod | grep -E "lpfc|qla2xxx|bnx2fc|bfa"

# If no driver is listed, load the appropriate module for your HBA:
#   Emulex/Broadcom LPe-series: lpfc
#   QLogic QLE-series:          qla2xxx
#   Broadcom NetXtreme FCoE:    bnx2fc
sudo modprobe lpfc       # or qla2xxx / bnx2fc

# Verify HBA ports are online
cat /sys/class/fc_host/host*/port_state
# Expected: Online

# Check link speed (verify cable / SFP negotiated correctly)
cat /sys/class/fc_host/host*/speed
# Example: 16 Gbit

# Discover your WWPNs — register these on the storage array
cat /sys/class/fc_host/host*/port_name
# Example: 0x2100001b32a1bcde
```

> **Register these WWPNs** with your storage array to authorize access. See Step 3.

