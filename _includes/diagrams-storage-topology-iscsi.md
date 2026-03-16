# Storage Network Topology (iSCSI)

## Recommended iSCSI Network Architecture

```mermaid
graph TB
    subgraph Host["Host Server"]
        APP[Applications/VMs]
        DM[dm-multipath]
        ISCSI[iSCSI Initiator]
        NIC1[NIC Port 1<br/>10.100.1.101]
        NIC2[NIC Port 2<br/>10.100.1.102]
    end

    subgraph Network["Storage Network (VLAN 100)"]
        SW1[Storage Switch 1]
        SW2[Storage Switch 2]
    end

    subgraph Storage["Everpure FlashArray"]
        CT0[Controller 0<br/>10.100.1.10]
        CT1[Controller 1<br/>10.100.1.11]
    end

    APP --> DM
    DM --> ISCSI
    ISCSI --> NIC1
    ISCSI --> NIC2
    NIC1 --> SW1
    NIC2 --> SW2
    SW1 --> CT0
    SW1 --> CT1
    SW2 --> CT0
    SW2 --> CT1

    style NIC1 fill:#90EE90
    style NIC2 fill:#90EE90
    style CT0 fill:#87CEEB
    style CT1 fill:#87CEEB
```

## Key Design Principles

### Redundancy at Every Level
- **Dual NICs**: Separate physical ports for each storage path
- **Dual Switches**: Eliminate single point of failure in network
- **Dual Controllers**: Active-active storage controllers

### Network Isolation
- **Dedicated VLAN**: Storage traffic isolated from management/VM traffic
- **Jumbo Frames**: MTU 9000 for optimal performance
- **No Routing**: Layer 2 connectivity between hosts and storage

## iSCSI Path Flow

```mermaid
flowchart LR
    subgraph Host
        A[Application] --> B[dm-multipath<br/>mpath0]
        B --> C[sda via Path 1]
        B --> D[sdb via Path 2]
        B --> E[sdc via Path 3]
        B --> F[sdd via Path 4]
    end
    
    subgraph Storage
        G[iSCSI Target<br/>Portal 1]
        H[iSCSI Target<br/>Portal 2]
    end
    
    C --> G
    D --> G
    E --> H
    F --> H
    
    style C fill:#90EE90
    style D fill:#90EE90
    style E fill:#87CEEB
    style F fill:#87CEEB
```

## Physical Cabling

| Component | Connection | Purpose |
|-----------|------------|---------|
| NIC Port 1 | Switch 1 | Primary iSCSI path |
| NIC Port 2 | Switch 2 | Secondary iSCSI path |
| Storage CT0 | Both Switches | Controller 0 connectivity |
| Storage CT1 | Both Switches | Controller 1 connectivity |

## Network Configuration Summary

| Parameter | Recommendation |
|-----------|----------------|
| MTU | 9000 (jumbo frames) |
| VLAN | Dedicated storage VLAN |
| Flow Control | Enabled (send/receive) |
| Speed | 10/25/100 GbE |
| Duplex | Full |

