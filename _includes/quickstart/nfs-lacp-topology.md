Each node carries one LACP bond built from two physical NICs, with one leg into each switch of an MLAG or VPC pair. The bond gives the node a single storage IP and survives the loss of a NIC, a cable, or an entire switch. Both arrays present a single NFS endpoint into the same storage VLAN.

```mermaid
flowchart TB
    subgraph NODES["Cluster nodes"]
        N1["Node 1<br/>bond0 — LACP 802.3ad<br/>nic1 + nic2"]
        N2["Node 2<br/>bond0 — LACP 802.3ad<br/>nic1 + nic2"]
    end

    subgraph NET["Storage fabric"]
        SW1["Switch 1"]
        SW2["Switch 2"]
    end

    subgraph ARRAYS["Everpure arrays"]
        FBVIP["FlashBlade<br/>Data VIP"]
        FAPORTS["FlashArray<br/>CT0 + CT1 ports"]
        FAVIF["FlashArray File VIF<br/>active on one controller"]
    end

    N1 --- SW1
    N1 --- SW2
    N2 --- SW1
    N2 --- SW2

    SW1 <-->|"MLAG / VPC"| SW2

    SW1 --- FBVIP
    SW2 --- FBVIP
    SW1 --- FAPORTS
    SW2 --- FAPORTS

    FAPORTS -.->|"VIF failover"| FAVIF

    style N1 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style N2 fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style SW1 fill:#34495e,stroke:#333,stroke-width:2px,color:#fff
    style SW2 fill:#34495e,stroke:#333,stroke-width:2px,color:#fff
    style FBVIP fill:#8e44ad,stroke:#333,stroke-width:3px,color:#fff
    style FAPORTS fill:#d35400,stroke:#333,stroke-width:2px,color:#fff
    style FAVIF fill:#8e44ad,stroke:#333,stroke-width:3px,color:#fff
```

Every link in the diagram is a dedicated storage VLAN at MTU 9000: node to switch, switch to switch, and switch to array. Each node contributes one bond leg to each switch, so no single switch, cable, or NIC is a single point of failure. The FlashArray File VIF is active on one controller at a time and migrates on controller failover; the FlashBlade data VIP is reachable through either switch.

Why bonding rather than two independent NICs: NFS presents a single server address, so the protocol has no path failover of its own. Block protocols do — iSCSI and NVMe-oF discover multiple portals and let the initiator or Portworx manage sessions across separate NICs, which is why those transports are often deployed without a bond. NFS has no equivalent, so link redundancy has to come from the OS bond underneath. A single unbonded NIC means a NIC failure is a storage outage.
