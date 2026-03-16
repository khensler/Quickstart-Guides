# Troubleshooting Flowcharts

Common troubleshooting diagrams for NVMe-TCP storage connectivity issues.

## NVMe-TCP Troubleshooting Flowchart

```mermaid
graph TD
    START[NVMe Issue Detected]

    START --> CHECK_PATHS{Are paths live?<br/>nvme list-subsys}

    CHECK_PATHS -->|No paths| CHECK_NET[Check Network<br/>Connectivity]
    CHECK_NET --> PING{Can ping<br/>storage portals?}
    PING -->|No| FIX_NET[Fix Network:<br/>- Check cables<br/>- Check switch config<br/>- Check interface IP]
    PING -->|Yes| CHECK_MOD{NVMe modules<br/>loaded?}
    CHECK_MOD -->|No| LOAD_MOD[Load modules:<br/>modprobe nvme-tcp]
    CHECK_MOD -->|Yes| CHECK_NQN[Verify Host NQN<br/>registered on array]

    CHECK_PATHS -->|Some paths| CHECK_PARTIAL[Check Failed Paths:<br/>- Interface down?<br/>- Portal unreachable?]

    CHECK_PATHS -->|All live| CHECK_PERF{Performance<br/>Issue?}

    CHECK_PERF -->|Yes| CHECK_MTU[Verify MTU 9000<br/>end-to-end]
    CHECK_MTU --> CHECK_POLICY[Check IO Policy:<br/>round-robin recommended]
    CHECK_POLICY --> CHECK_LOAD[Check Network<br/>Utilization]

    CHECK_PERF -->|No| CHECK_PERSIST{Persistence<br/>Issue?}

    CHECK_PERSIST -->|Yes| CHECK_SERVICE[Check nvmf-autoconnect<br/>service enabled]
    CHECK_SERVICE --> CHECK_CONFIG[Verify discovery.conf<br/>or config.d files]

    FIX_NET --> RECONNECT[Reconnect:<br/>nvme connect-all]
    LOAD_MOD --> RECONNECT
    CHECK_NQN --> RECONNECT
    CHECK_PARTIAL --> RECONNECT
    CHECK_LOAD --> TUNE[Tune Performance]
    CHECK_CONFIG --> ENABLE[Enable service:<br/>systemctl enable nvmf-autoconnect]

    RECONNECT --> VERIFY[Verify:<br/>nvme list-subsys]
    TUNE --> VERIFY
    ENABLE --> VERIFY

    style START fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style VERIFY fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## Quick Diagnostic Commands

| Command | Purpose |
|---------|---------|
| `nvme list-subsys` | Show subsystems and path status |
| `nvme list` | List connected namespaces |
| `nvme discover -t tcp -a <ip>` | Discover available subsystems |
| `cat /sys/class/nvme-subsystem/nvme-subsys*/iopolicy` | Check IO policy |
| `dmesg \| grep nvme` | NVMe kernel messages |
| `ip addr` | Network interface status |

