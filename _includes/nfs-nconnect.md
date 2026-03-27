### nconnect for Improved Throughput

The `nconnect` mount option creates multiple TCP connections per NFS mount, enabling parallel I/O operations and significantly improving throughput on high-speed networks.

#### How nconnect Works

By default, NFS uses a single TCP connection per mount point. This becomes a bottleneck on modern multi-core systems with high-speed networks because:

- A single TCP connection cannot fully saturate 25 GbE or faster links
- I/O operations are serialized through one connection
- CPU load is concentrated on a single core handling the connection

With `nconnect`, the NFS client establishes multiple TCP connections to the server. I/O requests are distributed across these connections, allowing:

- **Parallel I/O operations** — Multiple read/write requests can be in flight simultaneously
- **Better network utilization** — Multiple connections can approach line-rate on fast networks
- **Load distribution** — CPU load is spread across multiple cores

#### Recommended Values

| Network Speed | nconnect Value | Rationale |
|---------------|----------------|-----------|
| 10 GbE | 2-4 | Moderate parallelism, avoid overhead |
| 25 GbE | 4-8 | Balance throughput and connection overhead |
| 100 GbE | 8-16 | Maximum parallelism for high-bandwidth workloads |

> **Note:** Values above 16 rarely provide additional benefit and may increase memory overhead.

#### Linux Kernel Requirements

| Feature | Minimum Kernel |
|---------|----------------|
| `nconnect` support | 5.3+ |
| NFSv4.1 with nconnect | 5.3+ |
| NFSv4.2 with nconnect | 5.3+ |

**Distribution defaults:**

| Distribution | Default Kernel | nconnect Support |
|--------------|----------------|------------------|
| Debian 12 | 6.1 | ✅ Yes |
| RHEL 9 / Rocky 9 | 5.14 | ✅ Yes |
| SUSE 15 SP5+ | 5.14 | ✅ Yes |
| Oracle Linux 9 | 5.15 (UEK R7) | ✅ Yes |

#### Mount Examples

**Manual mount:**
```bash
mount -t nfs4 -o vers=4.1,hard,nconnect=4 10.21.148.147:/export /mnt/nfs
```

**fstab entry:**
```
10.21.148.147:/export /mnt/nfs nfs4 vers=4.1,hard,timeo=300,retrans=2,nconnect=4,_netdev 0 0
```

#### Verify nconnect is Active

```bash
# Check mount options
mount | grep nconnect

# View NFS server connections (shows connection count)
cat /proc/fs/nfsfs/servers

# Detailed connection info
cat /proc/fs/nfsfs/volumes
```

**Expected output with nconnect=4:**
```
NV:4 MN:4 ...
```
The `MN:4` indicates 4 connections are established.

#### Performance Considerations

- **LACP/Bond load balancing** — With bonded interfaces using LACP, each TCP connection may hash to a different physical link, improving aggregate throughput
- **FlashArray VIPs** — Pure Storage FlashArray distributes connections across controllers automatically
- **Diminishing returns** — Increasing nconnect beyond 8-16 rarely improves performance and adds memory overhead

#### Troubleshooting

If nconnect doesn't appear in mount options:

1. **Kernel too old** — Verify kernel 5.3 or later with `uname -r`
2. **NFSv3 mount** — nconnect requires NFSv4.x; add `vers=4.1`
3. **Server limitation** — Some older NFS servers may not benefit from multiple connections

