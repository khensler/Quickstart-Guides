---
layout: default
title: Failover Diagrams
---

# Failover Diagrams

Failover behavior diagrams for NVMe-TCP and iSCSI.

## NVMe-TCP Failover Sequence

```mermaid
sequenceDiagram
    participant App as Application
    participant NVMe as NVMe Multipath
    participant Path1 as Active Path 1
    participant Path2 as Standby Path 2
    participant Storage as Storage Array

    App->>NVMe: Write Request
    NVMe->>Path1: Route via Path 1
    Path1->>Storage: I/O Operation
    Storage->>Path1: Success
    Path1->>NVMe: Complete
    NVMe->>App: Success

    Note over Path1: Path 1 Fails

    App->>NVMe: Write Request
    NVMe->>Path1: Attempt Path 1
    Path1--xNVMe: Timeout/Error
    NVMe->>Path2: Automatic Failover
    Path2->>Storage: I/O Operation
    Storage->>Path2: Success
    Path2->>NVMe: Complete
    NVMe->>App: Success

    Note over Path1: Path 1 Recovers

    Path1->>NVMe: Path Available
    NVMe->>NVMe: Rebalance I/O
```

## iSCSI dm-multipath Failover Sequence

```mermaid
sequenceDiagram
    participant App as Application
    participant DM as dm-multipath
    participant Path1 as /dev/sda (Path 1)
    participant Path2 as /dev/sdb (Path 2)
    participant Target as iSCSI Target

    App->>DM: Write to /dev/mapper/mpathX
    DM->>Path1: Route via sda
    Path1->>Target: SCSI Command
    Target->>Path1: Success
    Path1->>DM: Complete
    DM->>App: Success

    Note over Path1: Path 1 Fails (Link Down)

    App->>DM: Write Request
    DM->>Path1: Attempt sda
    Path1--xDM: I/O Error
    Note over DM: multipathd marks path failed
    DM->>Path2: Failover to sdb
    Path2->>Target: SCSI Command
    Target->>Path2: Success
    Path2->>DM: Complete
    DM->>App: Success

    Note over Path1: Path 1 Recovers

    Path1->>DM: Path reinstated
    DM->>DM: failback=immediate
```

## Failover Timing

### NVMe-TCP Failover Parameters

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| `ctrl-loss-tmo` | 600s | 1800s | Time before controller considered lost |
| `reconnect-delay` | 10s | 10s | Delay between reconnection attempts |
| `nr_io_queues` | CPU count | - | Number of IO queues per controller |

### iSCSI Failover Parameters

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| `no_path_retry` | queue | 0 | Fail immediately vs queue forever |
| `path_checker` | - | tur | Health check method |
| `polling_interval` | 5s | 5s | Path check frequency |

## APD (All Paths Down) Behavior

```mermaid
graph TD
    APD[All Paths Down]
    
    subgraph "no_path_retry = queue (Default - NOT Recommended)"
        Q1[Queue I/O Forever]
        Q2[System Hangs]
        Q3[Manual Intervention Required]
        Q1 --> Q2 --> Q3
    end
    
    subgraph "no_path_retry = 0 (Recommended)"
        F1[Fail I/O Immediately]
        F2[Application Gets Error]
        F3[Application Can Retry or Report]
        F1 --> F2 --> F3
    end
    
    APD --> Q1
    APD --> F1
    
    style Q2 fill:#c0392b,stroke:#333,stroke-width:2px,color:#fff
    style F3 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

