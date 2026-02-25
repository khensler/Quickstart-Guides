> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Network Architecture Principles

1. **Dedicated Storage Network**: Always use dedicated physical or VLAN-isolated networks for storage traffic
   - *Why*: Isolates storage I/O from other network traffic; prevents bandwidth contention; enables QoS policies specific to storage; simplifies security and firewall rules

2. **No Single Points of Failure**: Redundant switches, NICs, and storage controllers
   - *Why*: Any single component can fail without impacting storage availability; enables zero-downtime maintenance; critical for production environments

3. **Proper Segmentation**: Separate storage traffic from management and VM traffic
   - *Why*: Prevents noisy neighbor problems; ensures storage performance is not affected by VM traffic spikes; improves security posture; simplifies network troubleshooting

4. **Optimized MTU**: Use jumbo frames (MTU 9000) end-to-end when possible
   - *Why*: Reduces CPU overhead and improves throughput by reducing packet count; lowers interrupt rate; recommended for high-performance storage (actual gains vary by workload)

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
- **Performance Impact**: Improved throughput for large sequential I/O (actual gains vary by workload; validate with benchmarks)
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
- **⚠️ Requires ARP configuration** (see [ARP Configuration for Same-Subnet Multipath](#arp-configuration-for-same-subnet-multipath) below)

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

### ARP Configuration for Same-Subnet Multipath

> ⚠️ **Critical for Same-Subnet Deployments:** When using multiple interfaces on the same subnet (Option A above), proper ARP configuration is **essential** to prevent routing issues that can break multipath.

#### The Problem

When multiple network interfaces are assigned IP addresses in the same subnet (e.g., `10.100.1.101` on ens1f0 and `10.100.1.102` on ens1f1), Linux's default ARP behavior can cause problems:

**Default Behavior (arp_ignore=0):**
```
Storage Portal 10.100.1.10 sends ARP: "Who has 10.100.1.101?"
Without arp_ignore: BOTH ens1f0 AND ens1f1 might respond
Result: Storage array gets confused about which MAC address to use
Impact: Packets may be sent to wrong interface, breaking multipath
```

**Why This Breaks Multipath:**
- Storage array may cache the wrong MAC address for an IP
- Traffic sent to one interface but routed through another (asymmetric routing)
- Breaks multipath path selection - kernel expects traffic on specific interfaces
- Causes intermittent connection failures and performance issues

#### The Solution: arp_ignore and arp_announce

**arp_ignore** controls which interfaces respond to ARP requests:

| Value | Behavior | Use Case |
|-------|----------|----------|
| **0** (default) | Reply to ARP requests on any interface | Single interface per subnet |
| **1** | Reply only if target IP is local address on incoming interface | Partial protection |
| **2** | Reply only if target IP is local address on incoming interface AND sender IP is in same subnet | **Recommended for multipath** |

**arp_announce** controls the source IP used when sending ARP requests:

| Value | Behavior | Use Case |
|-------|----------|----------|
| **0** (default) | Use any local address | May cause confusion |
| **1** | Avoid addresses not in target's subnet | Better behavior |
| **2** | Use best local address for this target | **Recommended for multipath** |

#### Configuration

**Create persistent sysctl configuration:**

```bash
# For NVMe-TCP storage
cat > /etc/sysctl.d/99-nvme-tcp-arp.conf << 'EOF'
# ARP configuration for storage multipath
# Prevents ARP responses on wrong interface when multiple NICs share same subnet

# For dedicated physical interfaces (adjust interface names as needed)
net.ipv4.conf.ens1f0.arp_ignore = 2
net.ipv4.conf.ens1f1.arp_ignore = 2
net.ipv4.conf.ens1f0.arp_announce = 2
net.ipv4.conf.ens1f1.arp_announce = 2

# For VLAN interfaces (uncomment if using VLANs)
#net.ipv4.conf.ens1f0.100.arp_ignore = 2
#net.ipv4.conf.ens1f1.100.arp_ignore = 2
#net.ipv4.conf.ens1f0.100.arp_announce = 2
#net.ipv4.conf.ens1f1.100.arp_announce = 2

# Global settings (applies to all interfaces)
net.ipv4.conf.all.arp_ignore = 2
net.ipv4.conf.default.arp_ignore = 2
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_announce = 2
EOF

# For iSCSI storage (same settings, different file name for clarity)
cat > /etc/sysctl.d/99-iscsi-arp.conf << 'EOF'
# ARP configuration for iSCSI multipath
net.ipv4.conf.ens1f0.arp_ignore = 2
net.ipv4.conf.ens1f1.arp_ignore = 2
net.ipv4.conf.ens1f0.arp_announce = 2
net.ipv4.conf.ens1f1.arp_announce = 2
net.ipv4.conf.all.arp_ignore = 2
net.ipv4.conf.default.arp_ignore = 2
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_announce = 2
EOF

# Apply settings immediately
sysctl -p /etc/sysctl.d/99-nvme-tcp-arp.conf
# or
sysctl -p /etc/sysctl.d/99-iscsi-arp.conf
```

#### Verification

```bash
# Verify settings are applied
sysctl net.ipv4.conf.ens1f0.arp_ignore
sysctl net.ipv4.conf.ens1f1.arp_ignore
# Expected output: net.ipv4.conf.ens1f0.arp_ignore = 2

# Test ARP behavior from another host on same subnet
arping -I <interface> 10.100.1.101
# Should only get response from ens1f0's MAC address, not ens1f1

# Monitor ARP traffic
tcpdump -i ens1f0 arp &
tcpdump -i ens1f1 arp &
# Each interface should only respond to ARP requests for its own IP

# Check ARP cache
ip neigh show
# Clear ARP cache if needed after configuration changes
ip neigh flush all
```

#### Why arp_ignore=2 is Critical for Storage Multipath

- **Ensures correct path selection**: Each interface only responds for its own IP
- **Prevents asymmetric routing**: Traffic sent to .101 always uses ens1f0, traffic to .102 always uses ens1f1
- **Maintains multipath integrity**: Storage array can reliably use all paths
- **Avoids connection confusion**: Each path remains distinct and predictable

#### When ARP Configuration is NOT Required

ARP configuration is **not needed** when using:
- **Different subnets** (Option B above): Each interface is in a different broadcast domain
- **Single storage interface**: No ARP confusion possible
- **Bonded interfaces**: Bond handles the single IP address

**Reference:** [Linux Virtual Server - ARP Configuration](https://kb.linuxvirtualserver.org/wiki/Using_arp_announce/arp_ignore_to_disable_ARP)
