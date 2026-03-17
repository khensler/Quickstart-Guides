### Mount Options

**Recommended mount options:**

| Option | Value | Description |
|--------|-------|-------------|
| `vers` | `4.1` | NFSv4.1 for session recovery during failover |
| `hard` | — | Retry indefinitely during failover (critical) |
| `timeo` | `300` | 30-second timeout before retransmit (deciseconds) |
| `retrans` | `2` | Retransmit attempts before major timeout |
| `nconnect` | `4-8` | Multiple TCP connections |
| `noatime` | — | Don't update access times |
| `nodiratime` | — | Don't update directory access times |
| `_netdev` | — | Wait for network before mounting |

**Example fstab entry:**
```
<VIP>:/export /mnt/nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime,_netdev 0 0
```

