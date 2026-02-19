---
layout: default
title: NVMe Multipath Diagrams
---

# NVMe Native Multipath Diagrams

Diagrams specific to NVMe native multipathing (not dm-multipath).

## Path Redundancy Model

```mermaid
flowchart TB
    subgraph "Linux Host"
        HOST[Host NQN]
        NIC1[NIC 1<br/>10.100.1.101]
        NIC2[NIC 2<br/>10.100.1.102]
    end

    subgraph "8 Redundant Paths"
        P1[Path 1: NIC1→Portal1]
        P2[Path 2: NIC1→Portal2]
        P3[Path 3: NIC1→Portal3]
        P4[Path 4: NIC1→Portal4]
        P5[Path 5: NIC2→Portal1]
        P6[Path 6: NIC2→Portal2]
        P7[Path 7: NIC2→Portal3]
        P8[Path 8: NIC2→Portal4]
    end

    subgraph "Storage Array - 10.100.1.0/24"
        SUBSYS[NVMe Subsystem<br/>Single Namespace]
        PORTAL1[Portal 1<br/>10.100.1.10]
        PORTAL2[Portal 2<br/>10.100.1.11]
        PORTAL3[Portal 3<br/>10.100.1.12]
        PORTAL4[Portal 4<br/>10.100.1.13]
    end

    HOST --> NIC1
    HOST --> NIC2

    NIC1 --> P1 --> PORTAL1
    NIC1 --> P2 --> PORTAL2
    NIC1 --> P3 --> PORTAL3
    NIC1 --> P4 --> PORTAL4

    NIC2 --> P5 --> PORTAL1
    NIC2 --> P6 --> PORTAL2
    NIC2 --> P7 --> PORTAL3
    NIC2 --> P8 --> PORTAL4

    PORTAL1 --> SUBSYS
    PORTAL2 --> SUBSYS
    PORTAL3 --> SUBSYS
    PORTAL4 --> SUBSYS

    style SUBSYS fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style HOST fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## Queue-Depth IO Policy

```mermaid
graph TB
    subgraph "Application Layer"
        APP[Application<br/>Generates I/O Requests]
    end

    subgraph "NVMe Multipath Driver"
        DRIVER[NVMe Multipath<br/>Queue-Depth Policy]
        CHECK{Check Queue Depth<br/>of All Paths}
        SELECT[Select Path with<br/>Lowest Queue Depth]
    end

    subgraph "Available Paths - Real-time Queue Status"
        PATH1[Path 1<br/>Queue: 5]
        PATH2[Path 2<br/>Queue: 2]
        PATH3[Path 3<br/>Queue: 8]
        PATH4[Path 4<br/>Queue: 1]
    end

    subgraph "Storage Array"
        STORAGE[NVMe Subsystem<br/>Processes I/O]
    end

    APP --> DRIVER
    DRIVER --> CHECK
    CHECK --> SELECT
    SELECT -->|Lowest Queue = 1| PATH4
    PATH4 --> STORAGE

    style DRIVER fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style PATH4 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## IO Policy Comparison

| Policy | Behavior | Best For |
|--------|----------|----------|
| **queue-depth** | Routes to path with lowest queue | Mixed workloads (recommended) |
| **round-robin** | Rotates through paths equally | Uniform latency paths |
| **numa** | Prefers NUMA-local paths | NUMA-optimized systems |

## Enabling Native Multipath

```bash
# Add kernel parameter
echo 'options nvme_core multipath=Y' > /etc/modprobe.d/nvme-tcp.conf

# Verify after reboot
cat /sys/module/nvme_core/parameters/multipath
# Output: Y
```

