### Hard vs Soft Mounts

Understanding the difference between `hard` and `soft` mount options is critical for ensuring data integrity and application behavior during storage failover events.

#### Test Results Summary

| Mount Type | Timeout Behavior | Data Integrity | Recovery |
|------------|------------------|----------------|----------|
| **hard** | I/O hangs indefinitely (confirmed 5+ min) | ✅ Guaranteed | ~12-21s after restore |
| **soft** | I/O fails after ~182s | ⚠️ Risk of corruption | Immediate (with error) |

#### Hard Mount (Recommended)

With `hard` mount, NFS operations wait indefinitely until the server responds:

```
mount -t nfs4 -o vers=4.1,hard,timeo=300,retrans=2 ...
```

**Behavior during outage:**
- I/O operations pause (hang) until server is reachable
- Applications block but do not receive errors
- After connectivity restores, I/O resumes automatically
- **No data loss or corruption**

**Test results:**
- 15-second simulated outage: I/O resumed in ~12 seconds after restore
- 5-minute simulated outage (no restore): I/O hung for entire 300 seconds
- After restore at 5 min mark: I/O completed in 21 seconds
- Exit code: 0 (success)
- **Confirmed: Hard mount waits indefinitely - no timeout**

**Use when:**
- Data integrity is critical (databases, VMs, critical applications)
- Brief storage failover is acceptable (Pure Storage: <1 second)
- Applications can tolerate I/O pauses

#### Soft Mount (Not Recommended for Most Workloads)

With `soft` mount, NFS operations fail with an error after timeout:

```
mount -t nfs4 -o vers=4.1,soft,timeo=300,retrans=2 ...
```

**Behavior during outage:**
- I/O operations wait for timeout period
- After `timeo × (retrans + 1)` ≈ 90-180 seconds, returns I/O error
- Application receives error and must handle it
- **Risk of data corruption if write operations fail**

**Test results:**
- Simulated outage (no restore): I/O failed after 182 seconds
- Error: `Input/output error`
- Exit code: 1 (failure)

**Use when:**
- Application can handle I/O errors gracefully
- Responsiveness is more important than data integrity
- Testing or development environments

#### Why Pure Storage Recommends Hard Mounts

1. **Sub-second failover**: Pure FlashArray controller failover completes in <1 second
2. **Data integrity**: Hard mounts guarantee no partial writes or corruption
3. **Transparent recovery**: Applications don't need error handling for storage events
4. **Session recovery**: NFSv4.1 maintains session state across failover

#### Timeout Calculation

The total timeout before soft mount returns an error:

```
Total timeout ≈ timeo × (retrans + 1) × TCP_RETRIES
```

With `timeo=300` (30 seconds) and `retrans=2`:
- NFS-level: 30s × 3 = 90 seconds minimum
- TCP-level retries add additional time
- Observed: ~182 seconds in testing

#### Mount Options Reference

| Option | Recommended | Description |
|--------|-------------|-------------|
| `hard` | ✅ Yes | Retry indefinitely (data integrity) |
| `soft` | ❌ No | Return error on timeout (risk of corruption) |
| `timeo=300` | ✅ Yes | 30-second timeout (deciseconds) |
| `retrans=2` | ✅ Yes | 2 retries before major timeout |
| `nconnect=4` | ✅ Yes | Multiple TCP connections for throughput |

#### Recovery Time Factors

After connectivity is restored, recovery time depends on:

1. **TCP retransmission timers**: Kernel TCP stack retry intervals
2. **NFS state recovery**: NFSv4.1 session re-establishment
3. **Server load**: Array's response time after failover
4. **Network path**: Latency and routing convergence

Observed recovery times:
- Pure FlashArray failover: <1 second (array-side)
- Client I/O resume: ~12 seconds (client-side detection and retry)

#### Proxmox Hypervisor Testing

When NFS storage is blocked at the Proxmox host level:

| Scenario | Guest VM Behavior | Result |
|----------|-------------------|--------|
| **60s outage** | Single write hung for 61s | ✅ Success (0 errors) |
| **Total writes** | 6,086 over 120s | 1 slow write |

**Key finding:** Guest VMs using NFS-backed storage experience I/O pauses but no errors. The hard mount (Proxmox default) ensures writes complete successfully after connectivity is restored.

