### Mount Options

**Recommended mount options:**

| Option | Value | Description |
|--------|-------|-------------|
| `vers` | `4.1` | NFSv4.1 for session recovery during failover |
| `hard` | — | Retry indefinitely during failover (critical for data integrity) |
| `timeo` | `300` | 30-second timeout before retransmit (deciseconds) |
| `retrans` | `2` | Retransmit attempts before major timeout |
| `nconnect` | `4-8` | Multiple TCP connections (requires kernel 5.3+) |
| `noatime` | — | Don't update access times |
| `nodiratime` | — | Don't update directory access times |
| `_netdev` | — | Wait for network before mounting |

> ⚠️ **Warning:** Do not use `soft` mount option in production. Soft mounts return I/O errors after timeout (~182 seconds with default settings), which can cause data corruption and application failures. Always use `hard` for data integrity.

**Example fstab entry:**
```
<VIP>:/export /mnt/nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,noatime,nodiratime,_netdev 0 0
```

**Failover behavior comparison:**

| Mount Type | During Outage | After Recovery | Data Integrity |
|------------|---------------|----------------|----------------|
| `hard` | I/O hangs (queued) | Resumes in ~12s | ✅ Guaranteed |
| `soft` | I/O fails after ~182s | Error returned | ⚠️ Risk of corruption |

