# Storage Topology Diagrams

Common storage topology diagrams for Linux storage documentation.

## Standard Deployment Topology

### NVMe-TCP Deployment

```mermaid
flowchart TB
    subgraph "Linux Hosts"
        HOST1[Linux Host 1<br/>2x Storage NICs]
        HOST2[Linux Host 2<br/>2x Storage NICs]
        HOST3[Linux Host 3<br/>2x Storage NICs]
    end
    
    subgraph "Storage Network"
        SW1[Storage Switch 1<br/>10/25/100 GbE]
        SW2[Storage Switch 2<br/>10/25/100 GbE]
    end
    
    subgraph "NVMe-TCP Storage Array"
        CTRL1[Controller 1<br/>Portal 1 & 2]
        CTRL2[Controller 2<br/>Portal 3 & 4]
        NVME[(NVMe Namespace)]
    end
    
    SW1 --- SW2

    HOST1 ---|NIC 1| SW1
    HOST1 ---|NIC 2| SW2
    HOST2 ---|NIC 1| SW1
    HOST2 ---|NIC 2| SW2
    HOST3 ---|NIC 1| SW1
    HOST3 ---|NIC 2| SW2
    
    SW1 --- CTRL1
    SW1 --- CTRL2
    SW2 --- CTRL1
    SW2 --- CTRL2
    
    CTRL1 --- NVME
    CTRL2 --- NVME

    style NVME fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style SW1 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style SW2 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
```

### iSCSI Deployment

```mermaid
flowchart TB
    subgraph "Linux Hosts"
        HOST1[Linux Host 1<br/>2x Storage NICs]
        HOST2[Linux Host 2<br/>2x Storage NICs]
        HOST3[Linux Host 3<br/>2x Storage NICs]
    end
    
    subgraph "Storage Network"
        SW1[Storage Switch 1<br/>10/25/100 GbE]
        SW2[Storage Switch 2<br/>10/25/100 GbE]
    end
    
    subgraph "iSCSI Storage Array"
        CTRL1[Controller 1<br/>Portal 1 & 2]
        CTRL2[Controller 2<br/>Portal 3 & 4]
        LUN[(iSCSI LUNs)]
    end
    
    SW1 --- SW2

    HOST1 ---|NIC 1| SW1
    HOST1 ---|NIC 2| SW2
    HOST2 ---|NIC 1| SW1
    HOST2 ---|NIC 2| SW2
    HOST3 ---|NIC 1| SW1
    HOST3 ---|NIC 2| SW2
    
    SW1 --- CTRL1
    SW1 --- CTRL2
    SW2 --- CTRL1
    SW2 --- CTRL2
    
    CTRL1 --- LUN
    CTRL2 --- LUN

    style LUN fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style SW1 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style SW2 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
```

## Key Design Principles

| Component | Best Practice |
|-----------|---------------|
| **Switches** | Dual switches for redundancy |
| **NICs** | Minimum 2 per host for multipath |
| **Controllers** | Dual controller array for HA |
| **Paths** | 2 NICs × 4 portals = 8 paths |

