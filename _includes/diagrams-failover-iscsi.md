# Failover Diagrams (iSCSI)

Failover behavior diagrams for iSCSI with dm-multipath.

## iSCSI/dm-multipath Failover Sequence

```mermaid
sequenceDiagram
    participant App as Application
    participant DM as dm-multipath
    participant Path1 as Active Path 1
    participant Path2 as Standby Path 2
    participant Storage as Storage Array

    App->>DM: Write Request
    DM->>Path1: Route via Path 1
    Path1->>Storage: SCSI I/O Operation
    Storage->>Path1: Success
    Path1->>DM: Complete
    DM->>App: Success

    Note over Path1: Path 1 Fails

    App->>DM: Write Request
    DM->>Path1: Attempt Path 1
    Path1--xDM: Timeout/Error
    DM->>Path2: Automatic Failover
    Path2->>Storage: SCSI I/O Operation
    Storage->>Path2: Success
    Path2->>DM: Complete
    DM->>App: Success

    Note over Path1: Path 1 Recovers

    Path1->>DM: Path Available
    DM->>DM: Rebalance I/O
```

## Failover Timing

### iSCSI Failover Parameters

| Parameter | Default | Recommended | Description |
|-----------|---------|-------------|-------------|
| `replacement_timeout` | 120s | 20s | Time before failing over to alternate path |
| `fast_io_fail_tmo` | 5s | 5s | Time before marking path as failed |
| `no_path_retry` | fail | queue | Behavior when all paths fail |
| `polling_interval` | 5s | 5s | Path checking frequency |

**Configure timeouts in /etc/iscsi/iscsid.conf:**
```bash
# Aggressive failover (faster, may cause false positives in busy networks)
node.session.timeo.replacement_timeout = 20

# Conservative failover (slower, more tolerant of network glitches)
node.session.timeo.replacement_timeout = 60
```

## Path States

```mermaid
stateDiagram-v2
    [*] --> active: Path Discovered
    active --> failed: I/O Errors
    failed --> active: Path Restored
    failed --> ghost: Prolonged Failure
    ghost --> active: Manual Recovery
    active --> [*]: Session Logout
    
    note right of active: Handling I/O
    note right of failed: Failover in Progress
    note right of ghost: Requires Intervention
```

## dm-multipath Path Groups

```mermaid
graph TB
    subgraph Application Layer
        APP[Application]
    end
    
    subgraph Device Mapper
        DM[dm-multipath<br/>mpath0]
    end
    
    subgraph Path Group 1 - Active
        P1[sda - active]
        P2[sdb - active]
    end
    
    subgraph Path Group 2 - Standby
        P3[sdc - standby]
        P4[sdd - standby]
    end
    
    subgraph Storage Array
        CT1[Controller 1]
        CT2[Controller 2]
    end
    
    APP --> DM
    DM --> P1
    DM --> P2
    DM -.-> P3
    DM -.-> P4
    P1 --> CT1
    P2 --> CT1
    P3 --> CT2
    P4 --> CT2
    
    style P1 fill:#90EE90
    style P2 fill:#90EE90
    style P3 fill:#FFE4B5
    style P4 fill:#FFE4B5
```

## Failback Behavior

**Automatic failback** (default for active/active arrays):
- When failed path recovers, I/O is automatically rebalanced
- No manual intervention required

**Manual failback** (for active/passive arrays):
```bash
# Check current path states
multipathd show paths

# Force path check
multipathd reconfigure

# Manually switch path group
multipathd switchgroup <multipath_device> <group_number>
```

