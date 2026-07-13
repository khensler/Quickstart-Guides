---
layout: default
title: Link Aggregation and Flow Balancing
---

# Link Aggregation and Flow Balancing

A reference guide covering how LAG protocols work at the packet level, how traffic is distributed across member links, and how to configure and verify even distribution in storage networks.

> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your switch platform and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

## Table of Contents

- [The Core Rule: LAG Does Not Balance Per-Packet](#the-core-rule-lag-does-not-balance-per-packet)
- [Hash Mode Quick Reference](#hash-mode-quick-reference)
- [Host Bond Mode Quick Reference](#host-bond-mode-quick-reference)
- [How the Hash Algorithm Works](#how-the-hash-algorithm-works)
- [Hash Modes in Detail](#hash-modes-in-detail)
  - [Layer 2 — MAC Address Hash](#layer-2--mac-address-hash)
  - [Layer 3 — IP Address Hash](#layer-3--ip-address-hash)
  - [Layer 3+4 — IP + Port Hash](#layer-34--ip--port-hash)
  - [Layer 2+3 — MAC + IP Hash](#layer-23--mac--ip-hash)
- [Host Bond Modes in Detail](#host-bond-modes-in-detail)
  - [802.3ad / LACP](#8023ad--lacp-linux-mode4)
  - [active-backup](#active-backup-linux-mode1)
  - [balance-alb](#balance-alb-linux-mode6)
  - [Open vSwitch: balance-slb and balance-tcp](#open-vswitch-balance-slb-and-balance-tcp)
- [Getting Distribution from a Single VIP](#getting-distribution-from-a-single-vip)
- [Diagnosing Imbalanced Links](#diagnosing-imbalanced-links)
- [Configuration Checklist](#configuration-checklist)

---

## The Core Rule: LAG Does Not Balance Per-Packet

Link Aggregation (LAG) combines multiple physical links into a single logical interface to increase bandwidth and provide redundancy. Understanding how LAG actually distributes traffic is critical — the default behavior surprises most administrators and is a common source of unexpected performance bottlenecks.

LAG distributes traffic per **flow**, not per packet. Every packet belonging to the same flow always travels over the same physical link. No exceptions.

A flow is defined by whichever header fields the hash algorithm is configured to use. As long as those fields are identical across packets, those packets are the same flow and stay on the same link — even if that link is completely saturated while others are idle.

> **⚠️ The Storage Implication:** A single NFS mount to a single VIP is one flow. No matter how many links are in your LAG, that mount uses exactly one link. See [Getting Distribution from a Single VIP](#getting-distribution-from-a-single-vip) below.

Per-flow consistency is intentional and necessary: TCP requires in-order packet delivery. If packets from the same connection crossed different links with different latencies, they would arrive out of order and trigger retransmits. Flow affinity is what makes LAG safe for TCP traffic.

---

## Hash Mode Quick Reference

| Mode | Fields Used | Entropy in Storage Environments | Common Vendor Names |
|------|-------------|----------------------------------|---------------------|
| **Layer 2** | Src MAC + Dst MAC | Very low — few array ports | `src-dst-mac`, `layer2` |
| **Layer 3** | Src IP + Dst IP | Low — single VIP destination | `src-dst-ip`, `layer3` |
| **Layer 3+4** | Src IP + Dst IP + Src Port + Dst Port | High — best for storage | `src-dst-ip-port`, `layer3+4` |
| **Layer 2+3** | MACs + IPs | Moderate | `layer2+3` |

**Recommendation for storage networks:** Use Layer 3+4 (`layer3+4`) on both the switch port-channel and the host bond. This gives the hash the most fields to work with and is the only mode that benefits from multiple TCP connections per mount (`nconnect`).

---

## Host Bond Mode Quick Reference

| Bond Mode | Load Balancing | Requires Switch Config | Use Case |
|-----------|---------------|------------------------|----------|
| **802.3ad / LACP (mode 4)** | Yes, across all active links | LACP port-channel | Production storage networks |
| **active-backup (mode 1)** | No — one link active at a time | None | Failover only, no throughput gain |
| **balance-alb (mode 6)** | TX + RX, no LACP | None | Simpler environments without LACP |
| **balance-slb (OVS)** | By source MAC | None | Open vSwitch / Proxmox |
| **balance-tcp (OVS)** | L3+L4 hash | LACP port-channel | Open vSwitch / Proxmox (best) |

---

## How the Hash Algorithm Works

### Packet-Level Walk-Through

When a packet arrives at a LAG member interface — on either the switch or a bonded host NIC — the hardware extracts specific fields from the packet headers, combines them into a hash value, and maps that hash to a physical link index.

The process for a typical Layer 3+4 hash:

```
Incoming packet headers:
  Ethernet:  Src MAC = aa:bb:cc:dd:ee:01   Dst MAC = aa:bb:cc:dd:ee:10
  IP:        Src IP  = 10.0.1.101          Dst IP  = 10.0.1.10
  TCP:       Src Port = 54321              Dst Port = 2049

Step 1 — Extract the configured fields (Layer 3+4):
  Fields: Src IP, Dst IP, Src Port, Dst Port

Step 2 — Compute hash (simplified XOR illustration):
  10.0.1.101 XOR 10.0.1.10 XOR 54321 XOR 2049
  = some 32-bit value, e.g. 0xA3C17F4E

Step 3 — Map to a link:
  LAG has 4 active links (index 0–3)
  0xA3C17F4E % 4 = 2
  → This packet uses physical link index 2

Step 4 — Every subsequent packet in this TCP session:
  Same Src IP, Dst IP, Src Port, Dst Port
  → Same hash → Same link → Consistent ordering guaranteed
```

This is why TCP works correctly over LAG — packet ordering is preserved per flow because all packets in a session stay on the same link.

### What Changes When the Hash Mode Changes

Using the same packet with **Layer 3 only** (`src-dst-ip`):

```
Fields: Src IP = 10.0.1.101,  Dst IP = 10.0.1.10

Hash: 10.0.1.101 XOR 10.0.1.10 = 0x0000007B = 123 decimal

4 links: 123 % 4 = 3  → link index 3

A second NFS mount from the SAME host to the SAME VIP:
  Src IP = 10.0.1.101,  Dst IP = 10.0.1.10
  Hash: same XOR → same value → link index 3

Result: both mounts go to link 3. Links 0, 1, and 2 carry zero storage traffic.
```

With **Layer 3+4** (`src-dst-ip-port`) and `nconnect=4`:

```
Mount 1 — Connection 1:  Src Port 51000  →  hash → link 0
Mount 1 — Connection 2:  Src Port 51001  →  hash → link 1
Mount 1 — Connection 3:  Src Port 51002  →  hash → link 2
Mount 1 — Connection 4:  Src Port 51003  →  hash → link 3

Result: all 4 links carry traffic from a single NFS mount to a single VIP.
```

This is the mechanism that makes `nconnect` effective on bonded interfaces — more connections means more unique source ports, which means more hash diversity, which means better link utilization.

---

## Hash Modes in Detail

### Layer 2 — MAC Address Hash

**Fields hashed:** Source MAC address, Destination MAC address (one or both, depending on configuration).

**How distribution happens:**
Each unique source or destination MAC gets a different hash value. Hosts and storage ports each have unique MACs, so traffic from different hosts to different array ports distributes across links.

**Why it fails for storage:**
In a typical storage deployment, one host talks to one or a few array VIPs. The number of unique MAC pairs is small — often just one. With a single host NIC bond talking to a single storage VIP, all traffic has the same src/dst MAC, hashes identically, and uses one link.

**When it is useful:**
Pure L2 environments with many diverse sources. Not useful for storage.

```
Example — 1 host, 1 storage VIP, 4-link LAG:
  Src MAC aa:bb:cc:dd:ee:01, Dst MAC aa:bb:cc:dd:ee:10
  Hash(aa:bb:cc:dd:ee:01, aa:bb:cc:dd:ee:10) % 4 = 1  (always the same result)
  → 100% of storage traffic on link 1, links 0/2/3 idle
```

---

### Layer 3 — IP Address Hash

**Fields hashed:** Source IPv4/IPv6 address, Destination IPv4/IPv6 address (one or both).

**How distribution happens:**
Different src/dst IP pairs produce different hash values. Traffic between different host IPs and different storage IPs spreads across links.

**Why it fails for storage (single VIP):**
If all storage traffic goes to a single VIP — common with NFS — the destination IP never changes. The only entropy comes from the source IP, which is also fixed for a single host. All traffic hashes identically.

**When it is useful:**
Environments with many hosts (diverse src IPs) or many storage endpoints (diverse dst IPs). Acceptable for multi-host environments accessing a storage array over many VIPs.

```
Example — 4 hosts, 1 storage VIP, 4-link LAG:
  Host A (10.0.1.101) → VIP (10.0.1.10):  hash % 4 = 2
  Host B (10.0.1.102) → VIP (10.0.1.10):  hash % 4 = 0
  Host C (10.0.1.103) → VIP (10.0.1.10):  hash % 4 = 3
  Host D (10.0.1.104) → VIP (10.0.1.10):  hash % 4 = 2
  → 3 links active, but link 1 still idle; not perfectly balanced
```

Distribution with Layer 3 depends on the actual IP values — it is not guaranteed to be even. With a small number of hosts the distribution is essentially random.

---

### Layer 3+4 — IP + Port Hash

**Fields hashed:** Source IP, Destination IP, Source Port, Destination Port (and sometimes protocol number).

**How distribution happens:**
The addition of TCP/UDP port numbers introduces the highest entropy available from a packet header. Each new TCP connection from the same host to the same VIP uses a different ephemeral source port, chosen by the OS from the range 32768–60999 on Linux by default. That different source port produces a different hash, which may land on a different link.

**Why this is the right choice for storage:**
It is the only mode that creates distribution even when src IP and dst IP are identical across all traffic. It is also the only mode that benefits from `nconnect` and multi-session configurations.

```
Example — 1 host, 1 storage VIP, 4-link LAG, nconnect=4:
  Session 1: 10.0.1.101:51000 → 10.0.1.10:2049  hash % 4 = 0  → link 0
  Session 2: 10.0.1.101:51004 → 10.0.1.10:2049  hash % 4 = 1  → link 1
  Session 3: 10.0.1.101:51008 → 10.0.1.10:2049  hash % 4 = 3  → link 3
  Session 4: 10.0.1.101:51012 → 10.0.1.10:2049  hash % 4 = 0  → link 0 (collision)
  → 3 of 4 links active
```

Hash collisions are normal and expected — ephemeral port values are not designed to produce perfectly even distribution, just high entropy. With enough connections, the statistical distribution tends toward even.

**Important limitation:** Port numbers are only present in the first fragment when IP fragmentation occurs. For storage workloads using standard MTU-sized frames without fragmentation, this is not a concern.

---

### Layer 2+3 — MAC + IP Hash

**Fields hashed:** Source MAC, Destination MAC, Source IP, Destination IP.

**How distribution happens:**
Combines MAC and IP entropy. Useful when there are diverse MAC addresses but few IP addresses, or vice versa.

**In storage environments:**
Offers slightly more entropy than L2 or L3 alone but still does not include port numbers. Inferior to L3+4 for storage workloads. Rarely the right choice when L3+4 is available.

---

## Host Bond Modes in Detail

### 802.3ad / LACP (Linux `mode=4`)

LACP (Link Aggregation Control Protocol, IEEE 802.3ad) is the standard dynamic protocol for LAG negotiation. Both the host and the switch exchange LACP PDUs (Protocol Data Units) to establish and maintain the aggregation. The switch creates a port-channel; the host creates a bond.

**How traffic is distributed:**
The host bond driver selects the outgoing link for each transmitted frame using its `xmit_hash_policy` setting. Received traffic is distributed by the switch using its own port-channel hash algorithm. Both sides must be configured consistently for even distribution in both directions.

```bash
# Recommended host bond configuration (Linux nmcli)
nmcli connection modify bond0 \
    bond.options "mode=802.3ad,miimon=100,xmit_hash_policy=layer3+4"
```

Available `xmit_hash_policy` options:

| Policy | Fields | Notes |
|--------|--------|-------|
| `layer2` | Src/dst MAC | Low entropy for storage |
| `layer2+3` | MAC + IP | Moderate entropy |
| `layer3+4` | IP + TCP/UDP port | **Recommended for storage** |
| `encap3+4` | L3+4 inside VXLAN/GRE | Use when traffic is tunneled |

**LACP timers:**
LACP exchanges keepalives to detect link failures. Two rates are available:

| Rate | Interval | Failover Detection |
|------|----------|--------------------|
| `slow` (default) | 30 seconds | ~90 seconds |
| `fast` | 1 second | ~3 seconds |

For storage networks, use `lacp_rate=fast`:

```bash
nmcli connection modify bond0 \
    bond.options "mode=802.3ad,miimon=100,xmit_hash_policy=layer3+4,lacp_rate=fast"
```

**Switch-side requirements:**
The switch ports must be members of an LACP port-channel in active or passive mode. Active mode sends LACP PDUs proactively; passive mode responds only. At least one side must be active.

```
# Cisco Nexus
interface port-channel10
  switchport mode trunk
  switchport trunk allowed vlan 100
  spanning-tree port type edge trunk

interface Ethernet1/1
  channel-group 10 mode active
interface Ethernet1/2
  channel-group 10 mode active

# Set hash algorithm (global on Nexus)
port-channel load-balance src-dst-ip-l4port
```

```
# Arista
interface Port-Channel10
  switchport mode trunk
  lacp rate fast

interface Ethernet1
  channel-group 10 mode active
interface Ethernet2
  channel-group 10 mode active

# Set hash algorithm
port-channel load-balance trident fields ip src-ip dst-ip src-port dst-port
```

---

### active-backup (Linux `mode=1`)

Only one link is active at a time. All traffic goes through the primary link. On failure, the bond promotes the next available link. No hash algorithm is involved and no switch configuration is required.

**This mode provides zero throughput increase.** Two 10 GbE links in active-backup give 10 GbE of throughput, not 20 GbE. Its only purpose is redundancy.

```
Link state:
  eth0 [ACTIVE]   — carries all traffic (10 Gbps)
  eth1 [STANDBY]  — carries zero traffic, waiting for failover
```

Use active-backup when switch LACP support is unavailable, or when strict traffic isolation between links is required for troubleshooting.

---

### balance-alb (Linux `mode=6`)

ALB (Adaptive Load Balancing) distributes transmit traffic using a per-destination MAC hash, and additionally rebalances receive traffic by periodically updating the ARP table to direct incoming traffic to different MAC addresses. No LACP or switch configuration is required.

**Limitation:** Receive-side balancing only works if the remote end honors ARP updates promptly. Storage arrays and switches with ARP caching may not rebalance receive traffic as expected, making the receive-side benefit unreliable in practice. Transmit-side balancing still works and provides some benefit.

---

### Open vSwitch: balance-slb and balance-tcp

These bond modes apply when using Open vSwitch (OVS), common in Proxmox and OpenStack environments.

#### balance-slb

Distributes flows by source MAC address. No LACP required. Similar limitations to Linux `layer2` hash — low entropy in storage environments with few host MACs. Adequate for failover; poor for throughput scaling.

#### balance-tcp

Distributes flows using L3+L4 hash, equivalent to Linux `layer3+4`. **Requires LACP** on the connected switch ports. This is the correct OVS bond mode for storage networks when LACP is available.

```
# Proxmox OVS bond configuration (/etc/network/interfaces)
auto vmbr0
iface vmbr0 inet static
    address 10.0.1.1/24
    ovs_type OVSBridge
    ovs_ports bond0

auto bond0
iface bond0 inet manual
    ovs_bridge vmbr0
    ovs_type OVSBond
    ovs_bonds eth0 eth1
    ovs_options bond_mode=balance-tcp lacp=active other_config:lacp-time=fast
```

---

## Getting Distribution from a Single VIP

Storage arrays commonly expose traffic through a small number of VIPs or a single per-subnet VIP. This is the lowest-entropy scenario for LAG balancing and the one most likely to produce a saturated single link with idle neighbors.

### Option 1: Layer 3+4 Hash + nconnect

Configure both the host bond and the switch port-channel to use L3+4 hashing. Then use `nconnect` to open multiple TCP connections per NFS mount. Each connection originates from a different ephemeral source port, producing a different hash.

```
Single VIP (10.0.1.10), nconnect=8, L3+4 hash, 4-link LAG:
  conn 1: sport 51000 → hash 0 → link 0  ✓
  conn 2: sport 51004 → hash 1 → link 1  ✓
  conn 3: sport 51008 → hash 2 → link 2  ✓
  conn 4: sport 51012 → hash 3 → link 3  ✓
  conn 5: sport 51016 → hash 0 → link 0  (collision — expected)
  conn 6: sport 51020 → hash 2 → link 2  (collision — expected)
  conn 7: sport 51024 → hash 1 → link 1  (collision — expected)
  conn 8: sport 51028 → hash 3 → link 3  (collision — expected)
  → All 4 links active, load roughly equal
```

### Option 2: Multiple VIPs Across Subnets

Configure the storage array with one VIP per subnet, and connect each host interface to a different subnet. Traffic to different VIPs has different destination IPs, ensuring different hash values even with L3-only hashing.

This is the approach Pure Storage FlashBlade uses natively — each subnet belongs to exactly one LAG, and VIPs are assigned per subnet. Each host interface connects to a different subnet, and traffic distributes naturally because the destination IP differs per connection.

### Option 3: Verify the Switch Hash Configuration

Misconfigured switch hashing is the most common cause of LAG imbalance in storage environments. Before changing anything else, verify the active hash policy:

```bash
# Cisco Nexus — show current load-balance method
show port-channel load-balance

# Cisco IOS
show etherchannel load-balance

# Arista
show port-channel load-balance

# Linux host — show bond transmit hash policy
cat /sys/class/net/bond0/bonding/xmit_hash_policy

# Linux host — show full bond state including LACP negotiation
cat /proc/net/bonding/bond0
```

---

## Diagnosing Imbalanced Links

When a LAG is not distributing traffic evenly, check interface counters directly to confirm which links are carrying load:

```bash
# Linux host — per-link TX/RX byte counters
for iface in eth0 eth1 eth2 eth3; do
    echo -n "$iface TX: "; cat /sys/class/net/$iface/statistics/tx_bytes
    echo -n "$iface RX: "; cat /sys/class/net/$iface/statistics/rx_bytes
done

# Live view with ip
watch -n 2 'ip -s link show eth0; ip -s link show eth1'

# Bond-level per-slave statistics
cat /proc/net/bonding/bond0 | grep -A5 "Slave Interface"
```

**What to look for:**
If one interface shows consistently higher counters while others are near zero, the hash is producing the same result for all flows. Common causes:

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| One link at 100%, others at 0% | Hash mode too narrow (L2 or L3) | Switch to L3+4 on both host and switch |
| One link at 100%, others at 0% | Single src/dst IP pair, no port diversity | Add `nconnect` to NFS mounts |
| Two links active, two idle | Hash producing only 2 distinct values | Verify switch hash matches host `xmit_hash_policy` |
| All links at 0% except one | LACP negotiation failed | Check LACP state (see below) |

```bash
# Check LACP negotiation status (Linux)
cat /proc/net/bonding/bond0 | grep -E "LACP|MII|Speed|Link"

# Confirm switch sees all members as active (Cisco Nexus)
show port-channel summary
show lacp neighbor

# Arista
show port-channel
show lacp peer
```

If `show port-channel summary` shows member ports as `(D)` (down) or `(s)` (suspended) instead of `(P)` (in port-channel, active), LACP negotiation has failed. Check that both sides are configured for active or passive mode and that the LACP rate matches.

---

## Configuration Checklist

| Component | Recommended Setting | Why |
|-----------|--------------------|----|
| Switch port-channel hash | `src-dst-ip-l4port` / `layer3+4` | Maximum entropy for storage flows |
| Host bond `xmit_hash_policy` | `layer3+4` | Matches switch; distributes by connection |
| Host bond mode | `802.3ad` (LACP mode 4) | Active-active with negotiation |
| LACP rate | `fast` (1 second) | Detects link failures in ~3 seconds |
| NFS `nconnect` | 4–8 per mount | Creates multiple flows per VIP for distribution |
| OVS bond mode | `balance-tcp` | L3+4 distribution with LACP in OVS environments |

> **Key insight:** The switch hash algorithm and the host bond `xmit_hash_policy` are independent settings. Both must be set to `layer3+4` for bidirectional flow distribution. A mismatch means traffic distributes well in one direction and poorly in the other.

---

## Related Guides

- [Network Architecture Concepts](../network-concepts.md) — Storage network design principles
- [NFS nconnect](../nfs-nconnect.md) — Configuring multiple connections per NFS mount
- [Multipath Concepts](../multipath-concepts.md) — Path redundancy and load balancing for block storage
