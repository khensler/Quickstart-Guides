> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Common Troubleshooting

### Connection Issues

#### No Connections Established

**Symptoms:**
- No devices appear after connection attempt
- `nvme list` shows no connected devices
- `nvme list-subsys` shows no subsystems

**Diagnosis:**
```bash
# Check network connectivity
ping <storage_portal_ip>

# Check if NVMe-TCP port is reachable
nc -zv <storage_portal_ip> 4420  # NVMe-TCP data port
nc -zv <storage_portal_ip> 8009  # NVMe-TCP discovery port

# Check firewall rules
iptables -L -n -v | grep -E "4420|8009"

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
   - Allow required ports: 4420 (data), 8009 (discovery)
   - Check both host and storage array firewalls
   - **Recommended:** For dedicated storage networks, use trusted zone to disable filtering on storage interfaces (reduces CPU overhead)

3. **Incorrect configuration:**
   - Verify portal IP addresses
   - Check subsystem NQN
   - Verify host NQN is registered on storage array

#### Connections Drop Intermittently

**Symptoms:**
- Connections establish but drop randomly
- I/O errors in logs
- `nvme list-subsys` shows paths going up and down

**Diagnosis:**
```bash
# Monitor connection state
watch -n 1 'nvme list-subsys'

# Check for network errors
ethtool -S <interface> | grep -i error

# Check system logs
journalctl -f | grep -i "nvme"

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
   - Increase ctrl_loss_tmo value
   - Check reconnect_delay setting

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
cat /sys/block/nvme0n1/queue/nr_requests

# Check for CPU bottlenecks
top
mpstat -P ALL 1

# Check network latency
ping <portal_ip>

# Check path status and IO policy
nvme list-subsys
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
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

4. **IO policy not optimal:**
   - Verify IO policy is `round-robin` for balanced distribution
   - Check ANA state if using ANA

#### Low Throughput

**Symptoms:**
- Throughput below expected
- Not utilizing all paths
- Network bandwidth underutilized

**Diagnosis:**
```bash
# Test raw throughput
fio --name=test --rw=read --bs=1M --size=10G --filename=/dev/nvme0n1

# Check network utilization
iftop -i <interface>

# Check all paths are active
nvme list-subsys

# Verify IO policy
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy
```

**Solutions:**
1. **Not using all paths:**
   - Verify IO policy is round-robin: `echo "round-robin" > /sys/class/nvme-subsystem/nvme-subsys0/iopolicy`
   - Ensure all connections are live

2. **Network bottleneck:**
   - Verify link speed: `ethtool <interface> | grep Speed`
   - Check for packet drops: `ethtool -S <interface>`
   - Verify flow control: `ethtool -a <interface>`

3. **I/O scheduler:**
   - Verify scheduler is 'none' for NVMe devices
   - Increase queue depth if needed

4. **CPU bottleneck:**
   - Check CPU utilization
   - Enable offload features
   - Distribute IRQs across CPUs

### NVMe Multipath Issues

#### Paths Showing as Non-Live

**Symptoms:**
- `nvme list-subsys` shows non-live paths
- Reduced path count
- Performance degradation

**Diagnosis:**
```bash
# Check path status
nvme list-subsys

# Check for errors
dmesg | grep -i "nvme.*error\|nvme.*fail"

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
   # Reconnect to subsystem
   nvme disconnect -n <subsystem_nqn>
   nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn>
   ```

3. **Discovery refresh:**
   ```bash
   # Re-run discovery
   nvme discover -t tcp -a <discovery_ip> -s 8009
   ```

### Boot and Persistence Issues

#### Connections Don't Persist After Reboot

**Symptoms:**
- Connections work manually but don't auto-connect on boot
- Storage not available after reboot

**Solutions:**
```bash
# Verify nvmf-autoconnect service exists and is enabled
systemctl status nvmf-autoconnect.service

# Enable auto-connect
systemctl enable nvmf-autoconnect.service

# Or create persistent connection via discovery.conf
cat >> /etc/nvme/discovery.conf << EOF
--transport=tcp --traddr=<portal_ip> --trsvcid=8009
EOF

systemctl restart nvmf-autoconnect
```

#### Network Interfaces Not Coming Up on Boot

**Symptoms:**
- Storage interfaces not configured after reboot
- Connections fail because interfaces are down

**Solutions:**
```bash
# Verify auto configuration
grep "auto <interface>" /etc/network/interfaces

# Or for NetworkManager
nmcli connection modify <connection> connection.autoconnect yes

# Enable networking service
systemctl enable NetworkManager  # or networking
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
nc -zv <ip> 4420                # Test NVMe-TCP port
```

**NVMe Storage:**
```bash
lsblk                           # List block devices
nvme list                       # List NVMe devices
nvme list-subsys                # List NVMe subsystems and paths
nvme discover -t tcp -a <ip>    # Discover subsystems
nvme smart-log /dev/nvme0n1     # Check device health
cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy  # Check IO policy
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
journalctl -u nvmf-autoconnect  # NVMe autoconnect logs
dmesg -T | grep nvme            # NVMe kernel messages
```

