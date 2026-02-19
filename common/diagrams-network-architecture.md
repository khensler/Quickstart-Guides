---
layout: default
title: Network Architecture Diagrams
---

# Network Architecture Diagrams

Common network architecture diagrams for storage connectivity.

## Host Network Architecture

```mermaid
flowchart LR
    subgraph "Linux Host"
        NIC1[Storage NIC 1<br/>10.100.1.101]
        NIC2[Storage NIC 2<br/>10.100.1.102]
    end

    subgraph "Storage Network - VLAN 100"
        SW1[Switch 1]
        SW2[Switch 2]
    end

    subgraph "Storage Array"
        P1[Portal 1<br/>10.100.1.10]
        P2[Portal 2<br/>10.100.1.11]
        P3[Portal 3<br/>10.100.1.12]
        P4[Portal 4<br/>10.100.1.13]
    end

    NIC1 ---|Path 1| SW1
    NIC2 ---|Path 2| SW2
    SW1 --- SW2
    SW1 --- P1
    SW1 --- P2
    SW1 --- P3
    SW1 --- P4
    SW2 --- P1
    SW2 --- P2
    SW2 --- P3
    SW2 --- P4

    style NIC1 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
    style NIC2 fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
    style SW1 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style SW2 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
```

## Network Isolation

```mermaid
graph TB
    subgraph "Management Network"
        MGMT[Management<br/>VLAN 10]
    end

    subgraph "Application Network"
        APP[Application Traffic<br/>VLAN 20-50]
    end

    subgraph "Storage Network - ISOLATED"
        STORAGE[Storage Network<br/>VLAN 100<br/>10.100.1.0/24]
    end

    subgraph "Linux Host"
        HOST[Linux Server]
    end

    HOST ---|Management NIC| MGMT
    HOST ---|Application NIC| APP
    HOST ---|Storage NIC 1 & 2| STORAGE

    style STORAGE fill:#c0392b,stroke:#333,stroke-width:2px,color:#fff
    style MGMT fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style APP fill:#1e8449,stroke:#333,stroke-width:2px,color:#fff
```

## Network Configuration Recommendations

| Setting | Recommendation | Why |
|---------|----------------|-----|
| **MTU** | 9000 (Jumbo Frames) | Reduces CPU overhead, improves throughput |
| **VLAN** | Dedicated storage VLAN | Isolates storage traffic |
| **Bonding** | Do NOT bond storage NICs | Preserves multipath redundancy |
| **Gateway** | None on storage interfaces | Storage traffic stays on local subnet |

## ARP Configuration for Same-Subnet Multipath

When using multiple interfaces on the same subnet, configure ARP settings:

```bash
# Required for same-subnet multipath
sysctl -w net.ipv4.conf.all.arp_ignore=2
sysctl -w net.ipv4.conf.all.arp_announce=2
```

See [ARP Configuration](./network-concepts.md#arp-configuration-for-same-subnet-multipath) for detailed explanation.

