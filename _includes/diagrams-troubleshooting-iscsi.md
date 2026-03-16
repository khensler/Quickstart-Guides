# Troubleshooting Diagrams (iSCSI)

Common troubleshooting diagrams for iSCSI connectivity issues.

## iSCSI Troubleshooting Flowchart

```mermaid
graph TD
    START[iSCSI Issue Detected]
    
    START --> CHECK_SESSION{Are sessions active?<br/>iscsiadm -m session}
    
    CHECK_SESSION -->|No sessions| CHECK_NET[Check Network<br/>Connectivity]
    CHECK_NET --> PING{Can ping<br/>storage portals?}
    PING -->|No| FIX_NET[Fix Network:<br/>- Check cables<br/>- Check switch config<br/>- Check interface IP]
    PING -->|Yes| CHECK_DISCOVERY{iSCSI discovery<br/>working?}
    CHECK_DISCOVERY -->|No| CHECK_TARGET[Verify target<br/>portal on array]
    CHECK_DISCOVERY -->|Yes| CHECK_IQN[Verify Host IQN<br/>registered on array]
    
    CHECK_SESSION -->|Some sessions| CHECK_PATHS{All paths<br/>active?<br/>multipath -ll}
    CHECK_PATHS -->|No| RECONNECT_PATH[Reconnect paths:<br/>iscsiadm -m node -L all]
    CHECK_PATHS -->|Yes| CHECK_PERF{Performance<br/>acceptable?}
    
    CHECK_SESSION -->|All sessions| CHECK_MULTIPATH{Multipath<br/>configured?}
    CHECK_MULTIPATH -->|No| CONFIG_MPATH[Configure dm-multipath]
    CHECK_MULTIPATH -->|Yes| CHECK_PERF
    
    CHECK_PERF -->|Poor| TUNE[Check:<br/>- Network utilization<br/>- Queue depths<br/>- I/O scheduler]
    CHECK_PERF -->|Good| RESOLVED[Issue Resolved]
    
    CHECK_SERVICE{Sessions persist<br/>after reboot?}
    CHECK_SERVICE -->|No| CHECK_STARTUP[Check node.startup<br/>= automatic]
    CHECK_STARTUP --> ENABLE[Enable services:<br/>systemctl enable iscsid iscsi]
    
    FIX_NET --> DISCOVER[Discover targets:<br/>iscsiadm -m discovery -t st -p IP]
    CHECK_TARGET --> DISCOVER
    CHECK_IQN --> LOGIN[Login to targets:<br/>iscsiadm -m node -L all]
    DISCOVER --> LOGIN
    
    LOGIN --> VERIFY[Verify:<br/>iscsiadm -m session<br/>multipath -ll]
    RECONNECT_PATH --> VERIFY
    CONFIG_MPATH --> VERIFY
    TUNE --> VERIFY
    ENABLE --> VERIFY
    
    VERIFY --> RESOLVED
```

## Multipath State Diagram

```mermaid
stateDiagram-v2
    [*] --> ready: Path Discovered
    ready --> active: I/O Assigned
    active --> ready: I/O Complete
    active --> failed: I/O Error
    failed --> active: Path Restored
    failed --> shaky: Intermittent
    shaky --> active: Stabilized
    shaky --> failed: Degraded Further
    ready --> [*]: Session Logout
    
    note right of active: Handling I/O
    note right of failed: Failover Active
    note right of shaky: Unstable Path
```

## Quick Reference Table

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `iscsiadm -m session` | Show active sessions |
| 2 | `iscsiadm -m session -P 3` | Detailed session info |
| 3 | `multipath -ll` | Show multipath status |
| 4 | `multipathd show paths` | Show all path states |
| 5 | `iostat -xz 1` | I/O statistics |
| 6 | `dmesg \| grep iscsi` | Check for errors |

