## Proxmox NFS Storage Configuration

### Default Proxmox NFS Mount Options

When adding NFS storage via `pvesm add nfs`, Proxmox uses these default mount options:

| Option | Default Value | Description |
|--------|---------------|-------------|
| `vers` | 4.1 | NFS protocol version |
| `hard` | yes | Retry indefinitely on failure |
| `timeo` | 600 | 60 second timeout (in deciseconds) |
| `retrans` | 2 | Number of retransmissions |
| `rsize` | 1048576 | Read block size (1MB) |
| `wsize` | 1048576 | Write block size (1MB) |

**Example mount from Proxmox:**
```
10.21.148.147:/export on /mnt/pve/storage type nfs4 (rw,relatime,vers=4.1,rsize=1048576,wsize=1048576,namlen=255,hard,fatal_neterrors=none,proto=tcp,timeo=600,retrans=2,sec=sys,...)
```

### Adding NFS Storage with pvesm

```bash
# Scan for available NFS exports
pvesm scan nfs <NFS_SERVER_IP>

# Add NFS storage with defaults (recommended)
pvesm add nfs <STORAGE_NAME> \
    --server <NFS_SERVER_IP> \
    --export <EXPORT_PATH> \
    --content images,rootdir,iso,backup

# Add with custom options (if needed)
pvesm add nfs <STORAGE_NAME> \
    --server <NFS_SERVER_IP> \
    --export <EXPORT_PATH> \
    --content images,rootdir \
    --options "vers=4.1,hard,timeo=300,retrans=2,nconnect=4"
```

### Failover Test Results

#### Host-Level NFS Outage (60 seconds)

| Metric | Value |
|--------|-------|
| **Simulated Outage** | 60 seconds |
| **Host I/O Behavior** | Hung (queued) |
| **Recovery Time** | 5 seconds after restore |
| **Total Hang Time** | 66 seconds |
| **Exit Code** | 0 (success) |

#### Guest VM Impact During Host NFS Outage

| Metric | Value |
|--------|-------|
| **Test Duration** | 120 seconds |
| **NFS Blocked** | 60 seconds (at host level) |
| **Total Guest Writes** | 6,086 |
| **Slow Writes (>1s)** | 1 |
| **Failed Writes** | 0 |
| **Observed Hang** | 61 seconds (1 write) |

**Key Observation:** The guest VM experienced a single 61-second I/O pause during the host-level NFS outage. The write completed successfully after connectivity was restored. No errors were returned to the guest OS.

### Proxmox vs Manual Mount Comparison

| Setting | Proxmox Default | Pure Storage Recommended |
|---------|-----------------|--------------------------|
| `vers` | 4.1 ✅ | 4.1 |
| `hard` | yes ✅ | yes |
| `timeo` | 600 (60s) | 300 (30s) |
| `retrans` | 2 ✅ | 2 |
| `nconnect` | not set | 4-8 |

> **Note:** Proxmox defaults are production-ready. The only optional enhancement is adding `nconnect=4` for improved throughput on multi-core systems.

### Adding nconnect to Proxmox NFS Storage

By default, Proxmox does not set `nconnect`. To enable it for improved throughput:

```bash
# Modify existing storage to add nconnect
pvesm set <STORAGE_NAME> --options "vers=4.1,hard,timeo=300,retrans=2,nconnect=4"

# Or specify when creating new storage
pvesm add nfs <STORAGE_NAME> \
    --server <NFS_SERVER_IP> \
    --export <EXPORT_PATH> \
    --content images,rootdir \
    --options "nconnect=4"
```

**Verify nconnect is active:**
```bash
mount | grep <STORAGE_NAME>
# Should show: ...nconnect=4...

cat /proc/fs/nfsfs/servers
# MN:4 indicates 4 connections per mount
```

### Guest VM Behavior Summary

When NFS storage becomes unavailable at the Proxmox host level:

1. **VM continues running** - The guest OS does not crash or freeze
2. **I/O operations pause** - Disk writes/reads hang but don't fail
3. **Automatic recovery** - Once NFS is available, I/O resumes
4. **No data loss** - Hard mount ensures write completion
5. **Transparent to applications** - Applications see a pause, not an error

This behavior is ideal for production workloads where data integrity is critical.

