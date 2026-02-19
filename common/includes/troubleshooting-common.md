> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Common Troubleshooting

### Connection Issues

#### No Connections Established

**Symptoms:**
- No devices appear after connection attempt
- `nvme list` or `iscsiadm -m session` shows no connections
- Multipath shows no devices

**Diagnosis:**
```bash
# Check network connectivity
ping <storage_portal_ip>

# Check if storage port is reachable
nc -zv <storage_portal_ip> 4420  # NVMe-TCP
nc -zv <storage_portal_ip> 3260  # iSCSI

# Check firewall rules
iptables -L -n -v | grep <port>

# Check routing
ip route get <storage_portal_ip>

# Verify interface is up
ip link show <storage_interface>
```

**Solutions:**
1. **Network connectivity issue:**
   - Verify cable connections
   - Check switch configuration
   - Verify VLAN configuration
   - Check MTU settings match end-to-end

2. **Firewall blocking:**
   - Allow required ports: NVMe-TCP (4420 data, 8009 discovery), iSCSI (3260)
   - Check both host and storage array firewalls
   - **Recommended:** For dedicated storage networks, use trusted zone to disable filtering on storage interfaces (reduces CPU overhead)

3. **Incorrect configuration:**
   - Verify portal IP addresses
   - Check subsystem NQN or target IQN
   - Verify host identifier is registered on storage array

#### Connections Drop Intermittently

**Symptoms:**
- Connections establish but drop randomly
- I/O errors in logs
- Multipath shows paths going up and down

**Diagnosis:**
```bash
# Monitor connection state
watch -n 1 'nvme list-subsys'  # NVMe-TCP
watch -n 1 'iscsiadm -m session'  # iSCSI

# Check for network errors
ethtool -S <interface> | grep -i error

# Check system logs
journalctl -f | grep -i "nvme\|iscsi\|multipath"

# Monitor packet drops
netstat -i
```

**Common causes:**
1. **Network instability:**
   - Check for packet loss: `ping -c 100 <portal_ip>`
   - Check for high latency: `ping -c 100 <portal_ip> | tail -1`
   - Verify no spanning tree issues on switches
   - Check for duplex mismatches: `ethtool <interface> | grep Duplex`

2. **MTU mismatch:**
   - Test MTU: `ping -M do -s 8972 <portal_ip>`
   - Verify MTU on all devices in path
   - Set consistent MTU end-to-end

3. **Timeout settings too aggressive:**
   - Increase timeout values
   - Check ctrl_loss_tmo (NVMe-TCP)
   - Check replacement_timeout (iSCSI)

### Performance Issues

#### High Latency

**Symptoms:**
- Slow I/O performance
- High await times in `iostat`
- Application timeouts

**Diagnosis:**
```bash
# Check I/O latency
iostat -x 1 5

# Monitor queue depth
cat /sys/block/<device>/queue/nr_requests

# Check for CPU bottlenecks
top
mpstat -P ALL 1

# Check network latency
ping <portal_ip>

# Check for path imbalance
multipath -ll
dmsetup status
```

**Solutions:**
1. **Network latency:**
   - Check for network congestion
   - Verify QoS settings
   - Check for routing issues
   - Verify jumbo frames enabled

2. **CPU bottleneck:**
   - Check IRQ distribution
   - Enable IRQ affinity
   - Verify offload features enabled

3. **Storage array issue:**
   - Check array performance metrics
   - Verify no controller failover in progress
   - Check for array-side bottlenecks

4. **Path imbalance:**
   - Verify multipath policy
   - Check path priorities
   - Ensure all paths are active

#### Low Throughput

**Symptoms:**
- Throughput below expected
- Not utilizing all paths
- Network bandwidth underutilized

**Diagnosis:**
```bash
# Test raw throughput
fio --name=test --rw=read --bs=1M --size=10G --filename=/dev/mapper/<device>

# Check network utilization
iftop -i <interface>

# Check multipath I/O distribution
dmsetup status

# Verify all paths active
multipath -ll | grep status
```

**Solutions:**
1. **Not using all paths:**
   - Verify multipath policy (use service-time or round-robin)
   - Check path priorities
   - Ensure queue_if_no_path is set

2. **Network bottleneck:**
   - Verify link speed: `ethtool <interface> | grep Speed`
   - Check for packet drops: `ethtool -S <interface>`
   - Verify flow control: `ethtool -a <interface>`

3. **I/O scheduler:**
   - Use 'none' for NVMe devices
   - Increase queue depth

4. **CPU bottleneck:**
   - Check CPU utilization
   - Enable offload features
   - Distribute IRQs across CPUs

### Multipath Issues

#### Paths Showing as Failed

**Symptoms:**
- `multipath -ll` shows failed paths
- Reduced path count
- Performance degradation

**Diagnosis:**
```bash
# Check path status
multipath -ll

# Check for errors
dmesg | grep -i "error\|fail"

# Check connection state
nvme list-subsys  # NVMe-TCP
iscsiadm -m session -P 3  # iSCSI

# Check network interface
ip link show <interface>
ethtool <interface>
```

**Solutions:**
1. **Network interface down:**
   ```bash
   ip link set <interface> up
   ```

2. **Connection lost:**
   ```bash
   # NVMe-TCP: Reconnect
   nvme disconnect -n <subsystem_nqn>
   nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn>
   
   # iSCSI: Restart session
   iscsiadm -m node -T <target_iqn> -p <portal_ip> --logout
   iscsiadm -m node -T <target_iqn> -p <portal_ip> --login
   ```

3. **Multipath daemon issue:**
   ```bash
   systemctl restart multipathd
   multipath -r  # Reload configuration
   ```

#### Device Not Appearing in Multipath

**Symptoms:**
- Device visible in `nvme list` or `lsscsi` but not in `multipath -ll`
- Single path instead of multiple paths

**Diagnosis:**
```bash
# Check if device is blacklisted
multipath -v3 -d  # Dry run with verbose output

# Check multipath configuration
cat /etc/multipath.conf

# Check device attributes
udevadm info --query=all --name=/dev/<device>
```

**Solutions:**
1. **Device blacklisted:**
   - Check blacklist section in `/etc/multipath.conf`
   - Ensure device is not excluded
   - Add device to blacklist_exceptions if needed

2. **Missing WWID:**
   ```bash
   # Regenerate WWID
   /lib/udev/scsi_id -g -u -d /dev/<device>
   
   # Reload multipath
   multipath -r
   ```

3. **Multipath not configured:**
   - Verify multipath.conf exists and is valid
   - Restart multipathd: `systemctl restart multipathd`

### Boot and Persistence Issues

#### Connections Don't Persist After Reboot

**Symptoms:**
- Connections work manually but don't auto-connect on boot
- Storage not available after reboot

**Solutions:**

**NVMe-TCP:**
```bash
# Verify systemd service exists
systemctl status nvme-connect@<subsystem_nqn>.service

# Enable auto-connect
systemctl enable nvme-connect@<subsystem_nqn>.service

# Or use discovery service
systemctl enable nvmf-autoconnect.service
```

**iSCSI:**
```bash
# Verify startup mode is automatic
iscsiadm -m node -T <target_iqn> -p <portal_ip> -o show | grep startup

# Set to automatic
iscsiadm -m node -T <target_iqn> -p <portal_ip> -o update -n node.startup -v automatic

# Enable iSCSI service
systemctl enable iscsid iscsi
```

#### Network Interfaces Not Coming Up on Boot

**Symptoms:**
- Storage interfaces not configured after reboot
- Connections fail because interfaces are down

**Solutions:**
```bash
# Verify auto configuration in /etc/network/interfaces
grep "auto <interface>" /etc/network/interfaces

# Add if missing
echo "auto <interface>" >> /etc/network/interfaces

# Or enable with systemd
systemctl enable networking
```

### Diagnostic Commands Reference

**Network:**
```bash
ip addr show                    # Show IP configuration
ip route show                   # Show routing table
ip link show                    # Show interface status
ethtool <interface>             # Show NIC settings
ping <ip>                       # Test connectivity
traceroute <ip>                 # Trace network path
nc -zv <ip> <port>              # Test port connectivity
```

**Storage:**
```bash
lsblk                           # List block devices
nvme list                       # List NVMe devices
nvme list-subsys                # List NVMe subsystems
iscsiadm -m session             # List iSCSI sessions
multipath -ll                   # List multipath devices
dmsetup ls                      # List device mapper devices
```

**Performance:**
```bash
iostat -x 1                     # I/O statistics
iotop                           # I/O by process
iftop -i <interface>            # Network bandwidth
top                             # CPU and memory
mpstat -P ALL 1                 # Per-CPU statistics
```

**Logs:**
```bash
journalctl -f                   # Follow system logs
dmesg -T                        # Kernel messages
tail -f /var/log/syslog         # System log
```

