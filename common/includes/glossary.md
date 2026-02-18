---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

# Storage Terminology Glossary

This glossary defines key terms used throughout the iSCSI and NVMe-TCP documentation.

---

## Common Storage Terms

### Volume
A logical unit of storage provisioned on a storage array. Volumes are presented to hosts as block devices. On Pure Storage arrays, volumes are thin-provisioned and can be resized dynamically.

### LUN (Logical Unit Number)
An identifier used to address a specific storage volume within a target. In iSCSI, each volume presented to a host is assigned a LUN number. The term "LUN" is often used interchangeably with "volume" in storage discussions.

### Multipath
A technique that uses multiple physical network paths between a host and storage array for redundancy and performance. If one path fails, I/O continues over remaining paths. See [Multipath Concepts](multipath-concepts.md) for detailed configuration.

### ALUA (Asymmetric Logical Unit Access)
A SCSI standard that allows storage arrays to indicate preferred paths for accessing volumes. Paths are designated as "active optimized" (preferred) or "active non-optimized" (available but not preferred). Multipath software uses ALUA information to prioritize paths.

### Path
A single network connection between a host interface and a storage portal. Multiple paths provide redundancy and can be used for load balancing.

### Failover
The automatic process of switching from a failed path to an active path when a connection fails. Properly configured multipath enables seamless failover without I/O interruption.

### APD (All Paths Down)
A condition where all paths to a storage device become unavailable simultaneously. Also known as "All Paths Dead" in some contexts. See [APD Events](iscsi-multipath-config.md#understanding-apd-all-paths-down-events) for recovery procedures.

---

## iSCSI-Specific Terms

### iSCSI (Internet Small Computer Systems Interface)
A protocol that enables SCSI commands to be sent over TCP/IP networks. iSCSI allows block-level storage access over standard Ethernet infrastructure.

### Initiator
The host-side component that initiates iSCSI connections to storage targets. In Linux, the open-iscsi package provides the initiator functionality. Each initiator is identified by a unique IQN.

### Target
The storage array component that receives iSCSI connections from initiators. A target can present multiple LUNs to connected initiators.

### IQN (iSCSI Qualified Name)
A unique identifier for iSCSI initiators and targets. Format: `iqn.YYYY-MM.reverse.domain:identifier`

**Examples:**
- Initiator: `iqn.1994-05.com.redhat:server01`
- Target: `iqn.2010-06.com.purestorage:flasharray.12345abc`

**Location on Linux hosts:** `/etc/iscsi/initiatorname.iscsi`

### Portal (iSCSI)
An IP address and TCP port combination that provides access to an iSCSI target. Default iSCSI port is **3260**.

**Example:** `10.100.1.10:3260`

A storage array typically has multiple portals across controllers for redundancy and performance.

### Session
An active connection between an iSCSI initiator and target. A session can contain multiple TCP connections for performance.

### Discovery
The process of querying a target to learn which volumes (LUNs) are available. Discovery can use the SendTargets method or iSNS (Internet Storage Name Service).

### CHAP (Challenge-Handshake Authentication Protocol)
An authentication mechanism for iSCSI that verifies initiator identity using a shared secret. CHAP can be unidirectional (target authenticates initiator) or bidirectional/mutual (both authenticate each other).

### Interface Binding
The practice of associating iSCSI sessions with specific network interfaces. Required for proper multipath operation to ensure each session uses a designated NIC.

---

## NVMe-TCP-Specific Terms

### NVMe (Non-Volatile Memory Express)
A high-performance storage protocol designed for flash storage. NVMe reduces latency and increases IOPS compared to SCSI-based protocols.

### NVMe-TCP (NVMe over TCP)
NVMe protocol transported over TCP/IP networks. Combines NVMe performance benefits with standard Ethernet infrastructure. Uses port **4420** for data connections.

### NVMe-oF (NVMe over Fabrics)
The specification that extends NVMe across network fabrics. NVMe-TCP is one transport option; others include NVMe-RDMA and NVMe-FC.

### NQN (NVMe Qualified Name)
A unique identifier for NVMe hosts and subsystems. Similar in purpose to iSCSI IQN.

**Format:** `nqn.YYYY-MM.reverse.domain:identifier` or `nqn.2014-08.org.nvmexpress:uuid:<UUID>`

**Examples:**
- Host NQN: `nqn.2014-08.org.nvmexpress:uuid:12345678-1234-1234-1234-123456789abc`
- Subsystem NQN: `nqn.2010-06.com.purestorage:flasharray.12345abc`

**Location on Linux hosts:** `/etc/nvme/hostnqn`

### Subsystem
An NVMe storage entity that contains one or more namespaces. Analogous to an iSCSI target. A subsystem is identified by its NQN.

### Namespace
An NVMe storage volume. Analogous to an iSCSI LUN. Each namespace within a subsystem is assigned a Namespace ID (NSID).

### Controller
The NVMe component that manages connections and I/O between a host and subsystem. Each connection to a subsystem creates a controller instance.

### Discovery Controller
A special NVMe controller (port **8009**) that provides information about available subsystems. Used for automatic discovery of storage resources.

### Portal (NVMe-TCP)
An IP address and TCP port combination that provides access to an NVMe subsystem. Default NVMe-TCP data port is **4420**; discovery port is **8009**.

**Example:** `10.100.1.10:4420`

A storage array typically has multiple portals across controllers for redundancy and performance. Each portal can serve multiple subsystems.

### Native NVMe Multipathing
Linux kernel-level multipathing for NVMe devices, enabled via `nvme_core multipath=Y`. Unlike dm-multipath (used for iSCSI), native NVMe multipathing presents a single device path (`/dev/nvmeXnY`) with the kernel managing multiple underlying paths automatically.

### IO Policy
The algorithm used by native NVMe multipathing to select which path to use for I/O operations.

**Options:**
- **queue-depth** (Recommended): Routes I/O to path with lowest queue depth
- **round-robin**: Alternates between paths
- **numa**: Prefers paths on the same NUMA node as the CPU

**Configuration:** Set via udev rule or sysfs: `/sys/class/nvme-subsystem/nvme-subsys*/iopolicy`

---

## Connection Parameters

### ctrl-loss-tmo (Controller Loss Timeout)
NVMe-TCP parameter specifying how long (in seconds) to wait for a controller to reconnect before declaring it permanently lost. Recommended: **1800** (30 minutes) for production.

### reconnect-delay
NVMe-TCP parameter specifying the delay (in seconds) between reconnection attempts after a connection failure. Recommended: **10** seconds.

### fast_io_fail_tmo
iSCSI/multipath parameter specifying how quickly to mark a path as failed after an I/O error. Recommended: **5** seconds.

### dev_loss_tmo
iSCSI/multipath parameter specifying how long to wait before removing a failed device entirely. Recommended: **30** seconds. Should be longer than fast_io_fail_tmo.

### no_path_retry
Multipath parameter controlling behavior when all paths to a device are down. Recommended: **0** (fail immediately) to prevent I/O hangs. See [APD Events](iscsi-multipath-config.md#understanding-apd-all-paths-down-events) for details.

---

## Network Terms

### MTU (Maximum Transmission Unit)
The largest packet size that can be transmitted on a network segment. Jumbo frames (MTU 9000) are recommended for storage networks to improve performance.

### VLAN (Virtual Local Area Network)
A logical network partition that isolates traffic. Storage networks often use dedicated VLANs for security and performance isolation.

### QoS (Quality of Service)
Network traffic prioritization. Storage VLANs should have high QoS priority to prevent I/O delays during network congestion.

---

## Quick Reference Table

| iSCSI Term | NVMe-TCP Equivalent | Description |
|------------|---------------------|-------------|
| IQN | NQN | Unique host/target identifier |
| Target | Subsystem | Storage entity presenting volumes |
| LUN | Namespace | Individual storage volume |
| Portal | Portal/Endpoint | IP:Port for connections |
| Initiator | Host | Client connecting to storage |
| dm-multipath | Native NVMe Multipath | Path redundancy mechanism |
| Default Port: 3260 | Data Port: 4420, Discovery: 8009 | TCP ports |

---

*For more information on specific topics, see the related documentation files linked throughout this glossary.*

