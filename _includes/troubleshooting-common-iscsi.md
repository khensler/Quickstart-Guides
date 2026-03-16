# Common Troubleshooting (iSCSI)

## Connection Issues

### Cannot Connect to Storage

**Symptoms:**
- No devices appear after connection attempt
- `iscsiadm -m session` shows no connections
- Multipath shows no devices

**Diagnostic steps:**
```bash
# Check network connectivity
ping <storage_portal_ip>

# Check if storage port is reachable
nc -zv <storage_portal_ip> 3260  # iSCSI

# Check if iSCSI target is discovered
iscsiadm -m discovery -t sendtargets -p <storage_portal_ip>
```

**Common causes:**
1. **Network misconfiguration:**
   - Verify IP addresses and subnet masks
   - Check VLAN tagging
   - Verify switch port configuration (speed, duplex)

2. **Firewall blocking:**
   - Allow required ports: iSCSI (3260)
   - Check both host and storage array firewalls
   - **Recommended:** For dedicated storage networks, use trusted zone to disable filtering on storage interfaces

3. **Storage array not configured:**
   - Verify target portal is configured
   - Check that host IQN is registered
   - Ensure volume is mapped to host

### Intermittent Disconnections

**Symptoms:**
- Sessions drop and reconnect
- I/O errors in logs
- Performance degradation

**Diagnostic steps:**
```bash
# Monitor connection state
watch -n 1 'iscsiadm -m session'

# Check session statistics
iscsiadm -m session -P 3

# Check system logs
journalctl -f | grep -i "iscsi\|multipath"

# Monitor packet drops
ip -s link show | grep -A 5 "ens1f"
```

**Common causes:**
1. **Network issues:**
   - Cable problems
   - Switch port errors
   - MTU mismatch

2. **Overloaded network:**
   - Check for bandwidth saturation
   - Verify QoS settings

3. **Timeout settings too aggressive:**
   - Increase timeout values
   - Check replacement_timeout (default: 120s)

## Performance Issues

### Slow I/O Performance

**Symptoms:**
- High latency
- Low throughput
- High await times in iostat

**Diagnostic steps:**
```bash
# Check I/O wait times
iostat -xz 1

# Check multipath load balancing
multipathd show paths format "%d %T %t %s"

# Network throughput test
iperf3 -c <storage_ip>
```

**Common causes:**
1. **Network congestion:**
   - Enable jumbo frames (MTU 9000)
   - Verify flow control settings

2. **Single path in use:**
   - Check multipath status
   - Verify path policy

3. **I/O scheduler:**
   - Use appropriate scheduler for SCSI devices
   - Increase queue depth if needed

## Multipath Issues

### Paths Not Detected

**Symptoms:**
- `multipath -ll` shows only one path
- `multipathd show paths` shows missing paths

**Solutions:**
```bash
# Rescan iSCSI sessions
iscsiadm -m session --rescan

# Rescan SCSI bus
for host in /sys/class/scsi_host/host*; do
    echo "- - -" > $host/scan
done

# Reload multipath
multipathd reconfigure

# Check multipath configuration
multipath -v3
```

### Path Flapping

**Symptoms:**
- Paths constantly switching between active and failed
- High I/O latency during transitions

**Diagnostic steps:**
```bash
# Check connection state
iscsiadm -m session -P 3

# Monitor path state changes
watch -n 1 'multipathd show paths'
```

**Solutions:**
1. Check cable connections
2. Review switch port statistics for errors
3. Adjust timeout parameters

## Storage Errors

### I/O Errors During Operation

**Symptoms:**
- `Buffer I/O error` in dmesg
- Application errors writing to storage

**Diagnostic steps:**
```bash
# Check connection state
iscsiadm -m session -P 3

# Check multipath status
multipathd show paths

# Check for SCSI errors
dmesg | grep -i "scsi\|iscsi" | tail -20
```

**Solutions:**
1. **Session lost:**
   ```bash
   # Logout and re-login iSCSI sessions
   iscsiadm -m node -U all
   iscsiadm -m node -L all
   ```

2. **Path degraded:**
   ```bash
   # Check and repair multipath
   multipathd show paths
   multipathd reconfigure
   ```

### Device Not Available After Reboot

**Symptoms:**
- Device visible in `lsscsi` but not in `multipath -ll`
- Single path instead of multiple paths

**Solutions:**
```bash
# Verify multipath service is running
systemctl status multipathd

# Check if devices are blacklisted
multipath -v3 2>&1 | grep -i blacklist

# Verify iSCSI sessions reconnect on boot
systemctl status iscsid
systemctl status iscsi
```

**Ensure iSCSI auto-login:**
```bash
# Enable auto-login for all targets
iscsiadm -m node -o update -n node.startup -v automatic

# Enable iSCSI services
systemctl enable iscsid
systemctl enable iscsi
```

## Quick Reference

### Common Commands
```bash
lsblk                           # List block devices
lsscsi                          # List SCSI devices
iscsiadm -m session             # List iSCSI sessions
iscsiadm -m session -P 3        # Detailed session info
multipath -ll                   # List multipath devices
multipathd show paths           # Show all paths
iostat -xz 1                    # I/O statistics
dmesg | grep -i iscsi           # Check for errors
```

### Service Management
```bash
systemctl status iscsid         # Check iSCSI initiator
systemctl restart iscsid        # Restart iSCSI
systemctl status multipathd     # Check multipath daemon
multipathd reconfigure          # Reload multipath config
```

