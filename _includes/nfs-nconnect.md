### nconnect for Improved Throughput

The `nconnect` option creates multiple TCP connections per mount:

| Network Speed | nconnect Value |
|---------------|----------------|
| 10 GbE | 2-4 |
| 25 GbE | 4-8 |
| 100 GbE | 8-16 |

**Verify nconnect:**
```bash
mount | grep nconnect
cat /proc/fs/nfsfs/servers
```

