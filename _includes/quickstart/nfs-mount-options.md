> **📘 Recommended Options:**
> - `vers=4.1` — NFSv4.1 for session recovery during controller failover
> - `hard` — Retry indefinitely during failover (prevents I/O errors)
> - `timeo=300,retrans=2` — 30-second timeout, ~90 seconds total before major retry (exceeds FlashArray <30s failover target)
> - `nconnect=4` — Multiple TCP connections for improved throughput (values 4-8 recommended)
> - `noatime,nodiratime` — Don't update access times, reducing metadata I/O
> - `_netdev` — Wait for network before mounting
>
> **During failover:** VM I/O pauses briefly (queued), then resumes automatically—no errors returned to applications.

