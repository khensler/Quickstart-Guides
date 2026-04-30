### NFS Virtual IP (VIP) and Controller Failover

Everpure FlashArray uses a **Virtual IP (VIP)** for NFS services:

1. **Single Active Controller**: The NFS VIP is hosted on one controller at a time
2. **Automatic Failover**: If the active controller fails, the VIP migrates to the standby
3. **Client Transparency**: NFS clients connect to the VIP—failover is transparent
4. **TCP Session Recovery**: NFSv4.1 supports session recovery after failover

#### FlashArray Failover Timing

| Event Type | Target Duration | Description |
|------------|-----------------|-------------|
| **Unplanned failover** | < 30 seconds | Controller failure, VIP migrates to standby |
| **Planned failover** | < 15 seconds | Non-disruptive operations (NDO), graceful migration |
| **Network path failure** | Immediate | Bonded NICs provide local redundancy |

#### Why `hard` Mount is Critical

```
soft mount:  Failover → Timeout → I/O ERROR → Data corruption risk
hard mount:  Failover → I/O pauses → VIP migrates → I/O resumes automatically
```

With `soft` mounts, if the VIP isn't available within the timeout, NFS returns errors to applications—this can corrupt databases, crash VMs, or lose data. **Always use `hard` mounts for production.**

#### Timeout Calculation

With `timeo=300` (30 seconds) and `retrans=2`:

| Phase | Duration | Cumulative |
|-------|----------|------------|
| Initial request | — | 0s |
| First timeout | 30s | 30s |
| First retransmit + timeout | 30s | 60s |
| Second retransmit + timeout | 30s | 90s |
| Major timeout reached | — | **~90 seconds** |

After major timeout, the client enters exponential backoff but **continues retrying indefinitely** with `hard` mount. This ensures VMs survive even extended maintenance windows.

> **Note:** The 90-second window comfortably exceeds FlashArray's <30 second failover target, providing margin for network reconvergence.

#### Impact on VM I/O During Failover

| Phase | VM Behavior | Duration |
|-------|-------------|----------|
| **Pre-failover** | Normal I/O | — |
| **Failover in progress** | I/O **pauses** (queued in kernel) | 10-30 seconds typical |
| **Post-failover** | Queued I/O completes, normal operation resumes | Automatic |

**What happens inside the VM:**
- Processes performing I/O will **block** (appear frozen)
- No I/O errors are returned to applications
- CPU-bound processes continue normally
- Network connections unrelated to NFS are unaffected
- After failover, all queued I/O completes in order

**Guest OS behavior:**
- Linux guests: Processes in "D" (uninterruptible sleep) state temporarily
- Windows guests: Applications may show "Not Responding" briefly
- Databases: Transactions pause but do not fail (with `hard` mount)

> **⚠️ Warning:** Using `soft` mounts converts the I/O pause into I/O errors, which can cause VM filesystem corruption, database crashes, or application failures.

