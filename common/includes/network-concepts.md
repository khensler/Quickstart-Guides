---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

## Network Architecture Principles

1. **Dedicated Storage Network**: Always use dedicated physical or VLAN-isolated networks for storage traffic
   - *Why*: Isolates storage I/O from other network traffic; prevents bandwidth contention; enables QoS policies specific to storage; simplifies security and firewall rules

2. **No Single Points of Failure**: Redundant switches, NICs, and storage controllers
   - *Why*: Any single component can fail without impacting storage availability; enables zero-downtime maintenance; critical for production environments

3. **Proper Segmentation**: Separate storage traffic from management and VM traffic
   - *Why*: Prevents noisy neighbor problems; ensures storage performance is not affected by VM traffic spikes; improves security posture; simplifies network troubleshooting

4. **Optimized MTU**: Use jumbo frames (MTU 9000) end-to-end when possible
   - *Why*: Reduces CPU overhead by ~30%; improves throughput by reducing packet count; lowers interrupt rate; essential for high-performance storage

### Network Topology Options

#### Option 1: Dedicated Physical Networks (Recommended)

**Why Recommended:**
This is the gold standard for production storage networks because it provides complete isolation and maximum performance.

**Advantages:**
- **Maximum performance and isolation**: Storage has dedicated bandwidth with zero contention
- **No contention with other traffic**: VM traffic spikes cannot impact storage performance
- **Simplified troubleshooting**: Storage network issues are isolated and easier to diagnose
- **Predictable latency**: Consistent performance without interference from other workloads

**Requirements:**
- Dedicated NICs on each node (minimum 2 for redundancy)
  - *Why 2 minimum*: Provides redundancy; one NIC can fail without storage outage
- Dedicated storage switches (minimum 2 for redundancy)
  - *Why 2 minimum*: Eliminates switch as single point of failure; allows switch maintenance without downtime
- Direct connections to storage array
  - *Why direct*: Reduces latency; simplifies network path; fewer points of failure

#### Option 2: VLAN-Based Segmentation (Shared NICs)

**When to Use:**
Choose this option when you have limited physical NICs or want to consolidate infrastructure. Acceptable for environments where cost/port density is a concern and you can accept some performance trade-offs.

**Advantages:**
- **Efficient use of physical infrastructure**: Reduces NIC and switch port requirements
- **Flexible network design**: Easy to add new VLANs without physical changes
- **Single set of NICs handles multiple traffic types**: Lower hardware costs; fewer cables

**Considerations:**
- **NICs are shared with management, VM, and container traffic**
  - *Impact*: Storage competes for bandwidth with other traffic; potential performance degradation during high VM traffic
- **Requires proper VLAN configuration and trunking on switches**
  - *Why critical*: Misconfiguration can cause traffic leakage or complete storage outage
- **Storage VLANs share bandwidth with other VLANs on same NICs**
  - *Impact*: Maximum storage throughput is limited by total NIC bandwidth minus other traffic
- **Requires QoS/traffic prioritization for storage VLANs**
  - *Why essential*: Without QoS, VM traffic can starve storage traffic causing I/O timeouts
- **Proper switch redundancy still required**
  - *Why*: Even with shared NICs, you still need redundant switches to avoid single point of failure

### MTU Configuration Best Practices

**Jumbo Frames (MTU 9000):**
- **Performance Impact**: 20-30% improvement in throughput for large sequential I/O
- **CPU Reduction**: Fewer packets to process means lower CPU overhead
- **Latency**: Slightly reduced latency for large transfers

**Requirements for Jumbo Frames:**
- **End-to-end configuration**: ALL devices in the path must support MTU 9000
  - Host NICs
  - All switches in the path
  - Storage array ports
- **Verification**: Test with ping to ensure no fragmentation
  ```bash
  # Test MTU 9000 (8972 bytes + 28 byte header = 9000)
  ping -M do -s 8972 <storage_portal_ip>
  ```

**When NOT to use Jumbo Frames:**
- Network infrastructure doesn't support it
- Mixed environments with devices that don't support it
- Troubleshooting network issues (start with MTU 1500, then increase)

### Network Performance Tuning

**NIC Ring Buffers:**
```bash
# Increase RX/TX ring buffers to reduce packet drops
ethtool -G <interface> rx 4096 tx 4096
```

**Interrupt Coalescing:**
```bash
# Reduce interrupt rate for better throughput (trade-off: slightly higher latency)
ethtool -C <interface> rx-usecs 50 tx-usecs 50
```

**RSS (Receive Side Scaling):**
```bash
# Distribute network processing across multiple CPU cores
ethtool -L <interface> combined 4
```

**Flow Control:**
```bash
# Enable flow control to prevent buffer overruns
ethtool -A <interface> rx on tx on
```

### IP Addressing Approaches

There are two valid approaches for assigning IP addresses to multiple storage interfaces:

#### Option A: Same Subnet (Recommended for Simplicity)

**Configuration:**
```
Interface 1: 10.100.1.101/24
Interface 2: 10.100.1.102/24
Storage Array: 10.100.1.10-19/24
```

**Advantages:**
- **Simpler routing**: All devices communicate directly without routing between subnets
- **Single VLAN**: Only one VLAN needed for storage traffic
- **Easy to understand**: Clear, sequential IP addressing scheme
- **Fewer firewall rules**: No inter-VLAN routing to configure

**Considerations:**
- Both interfaces are on the same L2 broadcast domain
- Requires careful planning to avoid IP conflicts
- Multipath relies on interface binding, not separate subnets

**Best for:** Proxmox clusters, environments with straightforward network design

#### Option B: Different Subnets (Recommended for Isolation)

**Configuration:**
```
Interface 1: 10.100.1.101/24 (VLAN 100)
Interface 2: 10.100.2.101/24 (VLAN 101)
Storage Array: 10.100.1.10/24 and 10.100.2.10/24
```

**Advantages:**
- **Network path isolation**: Each subnet can use different physical paths
- **Failure domain separation**: Issues in one subnet don't affect the other
- **Easier troubleshooting**: Clear separation of traffic per subnet
- **Required for some switch designs**: Necessary if using separate switch fabrics

**Considerations:**
- Storage array needs IPs in both subnets
- Requires two VLANs and potentially more complex switch configuration
- May need policy-based routing on hosts

**Best for:** Enterprise environments requiring strict network isolation

#### Choosing the Right Approach

| Factor | Same Subnet | Different Subnets |
|--------|------------|-------------------|
| **Network complexity** | Lower | Higher |
| **Failure isolation** | Shared L2 domain | Separate L2 domains |
| **Switch requirements** | Single VLAN | Multiple VLANs |
| **Multipath method** | Interface binding | Subnet-based paths |
| **Routing** | None required | May need policy routing |

**Important:** Both approaches work correctly with multipath. The key is:
- **iSCSI**: Uses interface binding in iscsiadm to ensure traffic uses specific interfaces
- **NVMe-TCP**: Uses `--host-iface` and `--host-traddr` parameters to bind connections to interfaces

Choose based on your network infrastructure requirements and organizational preferences.
