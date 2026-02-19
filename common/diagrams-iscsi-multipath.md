---
layout: default
title: iSCSI Multipath Diagrams
---

# iSCSI Multipath Diagrams

Diagrams specific to iSCSI with dm-multipath.

## iSCSI Path Redundancy Model

```mermaid
flowchart TB
    subgraph "Linux Host"
        INIT[iSCSI Initiator<br/>IQN]
        NIC1[NIC 1<br/>10.100.1.101]
        NIC2[NIC 2<br/>10.100.1.102]
    end

    subgraph "iSCSI Sessions - 4 Paths"
        S1[Session 1: NIC1→Portal1]
        S2[Session 2: NIC1→Portal2]
        S3[Session 3: NIC2→Portal1]
        S4[Session 4: NIC2→Portal2]
    end

    subgraph "dm-multipath Layer"
        MPATH["mpathX Device<br/>Aggregates All Paths"]
    end

    subgraph "iSCSI Storage Array"
        TARGET[iSCSI Target<br/>IQN]
        PORTAL1[Portal 1<br/>10.100.1.10]
        PORTAL2[Portal 2<br/>10.100.1.11]
        LUN[(LUN 0)]
    end

    INIT --> NIC1
    INIT --> NIC2

    NIC1 --> S1 --> PORTAL1
    NIC1 --> S2 --> PORTAL2
    NIC2 --> S3 --> PORTAL1
    NIC2 --> S4 --> PORTAL2

    S1 --> MPATH
    S2 --> MPATH
    S3 --> MPATH
    S4 --> MPATH

    PORTAL1 --> TARGET --> LUN
    PORTAL2 --> TARGET

    style MPATH fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
    style LUN fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
```

## dm-multipath Architecture

```mermaid
graph TB
    subgraph "Application Layer"
        APP[Application]
        FS["Filesystem<br/>mpathX"]
    end

    subgraph "Device Mapper - Multipath"
        DM[dm-multipath<br/>multipathd daemon]
        POLICY{Path Selection<br/>service-time 0}
    end

    subgraph "SCSI Layer"
        SDA["sda<br/>Path 1"]
        SDB["sdb<br/>Path 2"]
        SDC["sdc<br/>Path 3"]
        SDD["sdd<br/>Path 4"]
    end

    subgraph "iSCSI Sessions"
        ISCSI[iSCSI Initiator<br/>iscsid]
    end

    APP --> FS
    FS --> DM
    DM --> POLICY
    POLICY --> SDA
    POLICY --> SDB
    POLICY --> SDC
    POLICY --> SDD
    SDA --> ISCSI
    SDB --> ISCSI
    SDC --> ISCSI
    SDD --> ISCSI

    style DM fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style FS fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## ALUA Path States

```mermaid
graph LR
    subgraph "Active/Optimized Paths"
        AO1[Path 1<br/>prio=50]
        AO2[Path 2<br/>prio=50]
    end

    subgraph "Active/Non-Optimized Paths"
        ANO1[Path 3<br/>prio=10]
        ANO2[Path 4<br/>prio=10]
    end

    subgraph "dm-multipath"
        MPATH[mpathX<br/>service-time 0]
    end

    AO1 -->|Primary| MPATH
    AO2 -->|Primary| MPATH
    ANO1 -.->|Standby| MPATH
    ANO2 -.->|Standby| MPATH

    style AO1 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
    style AO2 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
    style ANO1 fill:#d4ac0d,stroke:#333,stroke-width:2px,color:#000
    style ANO2 fill:#d4ac0d,stroke:#333,stroke-width:2px,color:#000
```

## Key dm-multipath Settings

| Setting | Recommended Value | Purpose |
|---------|-------------------|---------|
| **no_path_retry** | 0 | Fail immediately when all paths down |
| **path_selector** | service-time 0 | Route based on path latency |
| **failback** | immediate | Return to optimal path when available |
| **path_checker** | tur | Test Unit Ready health check |

