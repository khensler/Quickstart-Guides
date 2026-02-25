---
layout: default
title: Troubleshooting Diagrams
---

# Troubleshooting Flowcharts

Common troubleshooting diagrams for storage connectivity issues.

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
    CHECK_MTU --> CHECK_POLICY[Check IO Policy:<br/>queue-depth recommended]
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

## iSCSI Troubleshooting Flowchart

```mermaid
graph TD
    START[iSCSI Issue Detected]

    START --> CHECK_SESSION{Active sessions?<br/>iscsiadm -m session}

    CHECK_SESSION -->|No sessions| CHECK_NET[Check Network<br/>Connectivity]
    CHECK_NET --> PING{Can ping<br/>storage portals?}
    PING -->|No| FIX_NET[Fix Network:<br/>- Check cables<br/>- Check interface config<br/>- Check VLAN]
    PING -->|Yes| DISCOVER[Rediscover targets:<br/>iscsiadm -m discovery]
    DISCOVER --> LOGIN[Login to targets:<br/>iscsiadm -m node -l]

    CHECK_SESSION -->|Sessions exist| CHECK_MPATH{Multipath<br/>healthy?<br/>multipath -ll}

    CHECK_MPATH -->|Degraded| CHECK_PATHS[Check failed paths:<br/>- Interface binding<br/>- iSCSI interface config]
    CHECK_PATHS --> RESCAN[Rescan sessions:<br/>iscsiadm -m session -R]

    CHECK_MPATH -->|All active| CHECK_PERF{Performance<br/>Issue?}

    CHECK_PERF -->|Yes| CHECK_MTU[Verify MTU 9000]
    CHECK_MTU --> CHECK_POLICY[Check path_selector:<br/>service-time 0]
    CHECK_POLICY --> CHECK_QUEUE[Check queue depth<br/>and timeouts]

    CHECK_PERF -->|No| CHECK_PERSIST{Persistence<br/>Issue?}

    CHECK_PERSIST -->|Yes| CHECK_STARTUP[Check node.startup=automatic]
    CHECK_STARTUP --> CHECK_SERVICES[Verify iscsid and<br/>multipathd enabled]

    FIX_NET --> LOGIN
    RESCAN --> VERIFY[Verify:<br/>multipath -ll]
    CHECK_QUEUE --> TUNE[Tune Settings]
    CHECK_SERVICES --> ENABLE[Enable services]
    
    LOGIN --> VERIFY
    TUNE --> VERIFY
    ENABLE --> VERIFY

    style START fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style VERIFY fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## Quick Diagnostic Commands

| Protocol | Command | Purpose |
|----------|---------|---------|
| **NVMe** | `nvme list-subsys` | Show subsystems and path status |
| **NVMe** | `nvme list` | List connected namespaces |
| **iSCSI** | `iscsiadm -m session` | Show active sessions |
| **iSCSI** | `multipath -ll` | Show multipath status |
| **Both** | `dmesg \| tail -50` | Recent kernel messages |
| **Both** | `ip addr` | Network interface status |

