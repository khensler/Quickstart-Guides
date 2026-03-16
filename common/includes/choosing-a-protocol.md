---
layout: default
title: Choosing a Storage Protocol
---

# Choosing a Storage Protocol

This guide helps you select the right storage protocol—**NVMe-TCP**, **iSCSI**, or **NFS**—for your environment.

---

## Quick Decision Flowchart

```mermaid
flowchart TD
    START([Start]) --> Q1{Need shared<br/>file access?}

    Q1 -->|Yes| NFS[**NFS**<br/>File protocol<br/>No LVM needed]
    Q1 -->|No| Q2{Minimize ops<br/>overhead?}

    Q2 -->|Yes| Q2a{Performance<br/>critical?}
    Q2 -->|No| Q3{Kernel supports<br/>NVMe-TCP?}

    Q2a -->|No| NFS
    Q2a -->|Yes| Q3

    Q3 -->|Yes| Q4{Need maximum<br/>performance?}
    Q3 -->|No| ISCSI[**iSCSI**<br/>Block protocol<br/>LVM required]

    Q4 -->|Yes| NVME[**NVMe-TCP**<br/>High-perf block<br/>LVM required]
    Q4 -->|No| Q5{Existing iSCSI<br/>infrastructure?}

    Q5 -->|Yes| ISCSI
    Q5 -->|No| NVME

    style NFS fill:#4a9eff,color:#fff
    style ISCSI fill:#50c878,color:#fff
    style NVME fill:#ff6b6b,color:#fff
```

---

## Protocol Comparison

| Feature | NVMe-TCP | iSCSI | NFS |
|---------|----------|-------|-----|
| **Type** | Block | Block | File |
| **Latency** | Lowest | Low | Moderate |
| **CPU Overhead** | Lowest | Low | Higher |
| **Multi-host Access** | Yes (complex)* | Yes (complex)* | Yes (native) |
| **Host-side Volume Mgmt** | Required (LVM) | Required (LVM) | None |
| **Kernel Version** | 5.0+ | Any | Any |
| **Protocol Maturity** | Newer | Mature | Mature |
| **Multipath** | Native (ANA) | dm-multipath | VIP failover |

*\*Block multi-host access requires thick LVM, clustered LVM (lvmlockd), and cluster filesystems (GFS2/OCFS2)—significantly more complex than NFS.*

---

## Operational Overhead

One of the most significant differences between block and file protocols is **operational complexity**.

### Block Protocols (NVMe-TCP, iSCSI)

Block protocols require host-side volume management:

```mermaid
flowchart LR
    subgraph ARRAY["Storage Array"]
        VOL1[Volume 1]
        VOL2[Volume 2]
        VOL3[Volume 3]
    end

    subgraph HOST["Linux Host"]
        MP[Multipath]
        LVM[LVM / Filesystem]
        APP[Application]
    end

    VOL1 --> MP
    VOL2 --> MP
    VOL3 --> MP
    MP --> LVM
    LVM --> APP

    style LVM fill:#ff6b6b,color:#fff
    style MP fill:#ff6b6b,color:#fff
```

**Management overhead:**
- Create/resize volumes on storage array
- Configure multipath on each host
- Create LVM physical volumes, volume groups, logical volumes
- Create and manage filesystems
- Resize operations require coordination (array → multipath → LVM → filesystem)

**Resource considerations:**
- Each volume consumes array resources (metadata, connections)
- Arrays have limits on volumes per host and total volumes
- Each host maintains multipath device maps and LVM metadata
- More volumes = more objects to monitor and manage

### NFS (File Protocol)

NFS provides a simpler operational model:

```mermaid
flowchart LR
    subgraph ARRAY["Storage Array"]
        EXPORT[NFS Export<br/>Single managed entity]
    end

    subgraph HOST["Linux Host"]
        MOUNT[NFS Mount]
        APP[Application]
    end

    EXPORT --> MOUNT
    MOUNT --> APP

    style MOUNT fill:#4a9eff,color:#fff
```

**Simpler operations:**
- Mount the export—no LVM, no multipath configuration
- Capacity managed at the export level (or thin provisioned)
- No per-volume management on hosts
- Add capacity without host-side changes

**Resource advantages:**
- Fewer array objects (one export vs. many volumes)
- No multipath device overhead on hosts
- No LVM CPU/memory overhead
- Easier monitoring (fewer entities)

### Multi-host Access with Block Protocols

Block protocols **can** support multi-host access through two approaches:

#### Option 1: Hypervisor-Managed (Proxmox, etc.)

Hypervisors like Proxmox can share block storage across nodes using **LVM thick**, with the hypervisor managing VM ownership:

```mermaid
flowchart TD
    subgraph ARRAY["Storage Array"]
        VOL[Shared Volume]
    end

    subgraph PVE["Proxmox Cluster"]
        subgraph NODE1["Node 1"]
            MP1[Multipath]
            LVM1[LVM Thick]
            VM1[VM A - Active]
        end

        subgraph NODE2["Node 2"]
            MP2[Multipath]
            LVM2[LVM Thick]
            VM2[VM B - Active]
        end

        PMXC[Proxmox Cluster<br/>manages VM ownership]
    end

    VOL --> MP1
    VOL --> MP2
    MP1 --> LVM1 --> VM1
    MP2 --> LVM2 --> VM2
    PMXC -.-> VM1
    PMXC -.-> VM2

    style PMXC fill:#e85a1b,color:#fff
    style VM1 fill:#4a9eff,color:#fff
    style VM2 fill:#4a9eff,color:#fff
```

**How it works:**
- All nodes see the shared LVM volume group
- Proxmox cluster tracks which node owns each VM
- Only one node accesses a VM's disk at a time
- Live migration transfers ownership between nodes
- No cluster filesystem needed—hypervisor coordinates access

**Requirements:**
- **LVM thick (not thin)** — LVM-thin does not support shared access
- Each VM disk is a separate logical volume
- Proxmox manages locking and coordination

**Advantages:**
- Simpler than full cluster filesystem stack
- Hypervisor handles HA and live migration
- Block-level performance for VMs

**Trade-offs:**
- No thin provisioning (capacity allocated upfront)
- More array volumes if using per-VM volumes on array

#### Option 2: Cluster Filesystem (GFS2/OCFS2)

**May not be supported by hypervio

For concurrent file access from multiple hosts (not hypervisor VMs), a full cluster stack is required:

```mermaid
flowchart TD
    subgraph ARRAY["Storage Array"]
        VOL[Shared Volume]
    end

    subgraph HOST1["Host 1"]
        MP1[Multipath]
        CLVM1[Clustered LVM<br/>lvmlockd]
        GFS1[GFS2 / OCFS2]
    end

    subgraph HOST2["Host 2"]
        MP2[Multipath]
        CLVM2[Clustered LVM<br/>lvmlockd]
        GFS2a[GFS2 / OCFS2]
    end

    subgraph CLUSTER["Cluster Infrastructure"]
        DLM[Distributed Lock Manager]
        COROSYNC[Corosync / Pacemaker]
    end

    VOL --> MP1
    VOL --> MP2
    MP1 --> CLVM1 --> GFS1
    MP2 --> CLVM2 --> GFS2a
    CLVM1 <--> DLM
    CLVM2 <--> DLM
    GFS1 <--> DLM
    GFS2a <--> DLM
    DLM <--> COROSYNC

    style CLVM1 fill:#ff6b6b,color:#fff
    style CLVM2 fill:#ff6b6b,color:#fff
    style GFS1 fill:#ff6b6b,color:#fff
    style GFS2a fill:#ff6b6b,color:#fff
```

**Requirements:**

| Component | Purpose |
|-----------|---------|
| **Thick LVM** | Thin LVM requires hypervisor coordination; thick for raw cluster FS |
| **Clustered LVM (lvmlockd)** | Coordinates LVM metadata across hosts |
| **Cluster filesystem (GFS2/OCFS2)** | Provides concurrent file access with distributed locking |
| **Distributed Lock Manager (DLM)** | Coordinates locks across cluster nodes |
| **Cluster stack (Corosync/Pacemaker)** | Manages cluster membership and fencing |

#### When to Use Each Approach

| Use Case | Recommended Approach |
|----------|---------------------|
| VM storage across hypervisor cluster | Hypervisor-managed (Proxmox LVM thick) |
| Oracle RAC, clustered databases | Cluster filesystem or raw block |
| Shared file access across Linux hosts | NFS (simplest) or GFS2/OCFS2 |
| General shared storage | NFS |

### Comparison Summary

| Aspect | Block (NVMe-TCP/iSCSI) | NFS |
|--------|------------------------|-----|
| **New capacity** | Create volume → configure multipath → create PV → extend VG → create/extend LV → create/extend FS | Use available space |
| **Host setup** | Multipath + LVM + filesystem | Mount command |
| **Resize operation** | Multi-step coordination | Automatic (thin) or export resize |
| **Array objects** | Many volumes per host | Single export per use case |
| **Array limits** | Volume count limits apply | Fewer objects, higher scale |
| **Monitoring** | Per-volume metrics | Per-export metrics |
| **Multi-host access** | Requires thick LVM + cluster FS + DLM | Native, no extra components |

---

## When to Use Each Protocol

### NVMe-TCP

**Best for:** High-performance workloads requiring the lowest latency.

✅ **Use when:**
- Running databases, analytics, or latency-sensitive applications
- Your kernel supports NVMe-TCP (Linux 5.0+)
- You need the most efficient CPU utilization
- You have capacity for LVM/multipath management
- Multi-host clustering with thick LVM + GFS2/OCFS2 is acceptable

❌ **Avoid when:**
- Running older kernels without NVMe-TCP support
- You want simple multi-host access (use NFS instead)
- Operational simplicity is a priority

---

### iSCSI

**Best for:** General-purpose block storage with broad compatibility.

✅ **Use when:**
- You have existing iSCSI infrastructure and expertise
- Running older kernels without NVMe-TCP support
- Broad tool and monitoring compatibility is needed
- Boot from SAN is required
- Multi-host clustering with thick LVM + GFS2/OCFS2 is acceptable

❌ **Avoid when:**
- Maximum performance is critical (use NVMe-TCP instead)
- You want simple multi-host access (use NFS instead)
- You want to minimize volume management overhead

---

### NFS

**Best for:** Shared file access with minimal operational overhead.

✅ **Use when:**
- Multiple hosts need concurrent access without cluster complexity
- Running VM images from shared storage (Proxmox, XCP-ng)
- Workloads benefit from file-level access (media files, home directories)
- Operational simplicity is a priority
- You want to minimize array object count
- Capacity needs to grow dynamically without host changes

❌ **Avoid when:**
- Running latency-sensitive databases (use block protocols)
- Maximum single-stream throughput is critical
- Application requires raw block device access

---

## Protocol Architecture

```mermaid
flowchart LR
    subgraph HOST["Linux Host"]
        APP[Application]
        FS[Filesystem]
        BLOCK[Block Layer]
        NVME_D[NVMe Driver]
        ISCSI_D[iSCSI Initiator]
        NFS_C[NFS Client]
    end

    subgraph NETWORK["Network"]
        TCP[TCP/IP]
    end

    subgraph ARRAY["Storage Array"]
        NVME_T[NVMe-TCP Target]
        ISCSI_T[iSCSI Target]
        NFS_S[NFS Server]
        STORAGE[(Storage)]
    end

    APP --> FS
    FS --> BLOCK
    FS --> NFS_C
    BLOCK --> NVME_D
    BLOCK --> ISCSI_D
    NVME_D --> TCP
    ISCSI_D --> TCP
    NFS_C --> TCP
    TCP --> NVME_T
    TCP --> ISCSI_T
    TCP --> NFS_S
    NVME_T --> STORAGE
    ISCSI_T --> STORAGE
    NFS_S --> STORAGE

    style NVME_D fill:#ff6b6b,color:#fff
    style ISCSI_D fill:#50c878,color:#fff
    style NFS_C fill:#4a9eff,color:#fff
    style NVME_T fill:#ff6b6b,color:#fff
    style ISCSI_T fill:#50c878,color:#fff
    style NFS_S fill:#4a9eff,color:#fff
```

---

## Use Case Examples

| Use Case | Recommended | Reason |
|----------|-------------|--------|
| Production databases | NVMe-TCP | Lowest latency, best IOPS |
| VM storage (shared) | NFS | Multi-host access, no per-VM volumes |
| VM storage (dedicated) | NVMe-TCP or iSCSI | Block performance, single host |
| Boot volumes | iSCSI | Broad bootloader support |
| File shares | NFS | Native file access, no LVM |
| Kubernetes PVs | NVMe-TCP or iSCSI | CSI drivers use block |
| Legacy applications | iSCSI | Compatibility with older systems |
| Media/video editing | NFS | Concurrent access, simple capacity |
| Large VM fleet | NFS | Fewer array objects to manage |
| Dev/test environments | NFS | Fast provisioning, minimal setup |
| High-scale deployments | NFS | Avoid per-host volume limits |

---

## Kernel Support Matrix

| Protocol | Minimum Kernel | Recommended |
|----------|---------------|-------------|
| NVMe-TCP | 5.0 | 5.14+ |
| iSCSI | 2.6 | Any current |
| NFS v4.1 | 2.6.31 | 5.4+ (nconnect) |

Check your kernel version:
```bash
uname -r
```

---

## Next Steps

Once you've chosen a protocol, see the distribution-specific guides:

- **NVMe-TCP:** [RHEL](../distributions/rhel/nvme-tcp/QUICKSTART.md) | [Debian](../distributions/debian/nvme-tcp/QUICKSTART.md) | [SUSE](../distributions/suse/nvme-tcp/QUICKSTART.md) | [Oracle](../distributions/oracle/nvme-tcp/QUICKSTART.md) | [Proxmox](../distributions/proxmox/nvme-tcp/QUICKSTART.md)
- **iSCSI:** [RHEL](../distributions/rhel/iscsi/QUICKSTART.md) | [Debian](../distributions/debian/iscsi/QUICKSTART.md) | [SUSE](../distributions/suse/iscsi/QUICKSTART.md) | [Oracle](../distributions/oracle/iscsi/QUICKSTART.md) | [Proxmox](../distributions/proxmox/iscsi/QUICKSTART.md)
- **NFS:** [RHEL](../distributions/rhel/nfs/QUICKSTART.md) | [Debian](../distributions/debian/nfs/QUICKSTART.md) | [SUSE](../distributions/suse/nfs/QUICKSTART.md) | [Oracle](../distributions/oracle/nfs/QUICKSTART.md) | [Proxmox](../distributions/proxmox/nfs/QUICKSTART.md)

