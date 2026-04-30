## Quick Reference

### Essential Commands

```bash
# Mount operations (with failover-optimized options)
mount -t nfs4 -o vers=4.1,hard,timeo=300,retrans=2,nconnect=4 <server>:<export> <mount>
umount <mount>

# Status
mount | grep nfs
nfsstat -c
nfsstat -m

# Troubleshooting
showmount -e <server>
rpcinfo -p <server>
```

### Configuration Files

| File | Purpose |
|------|---------|
| `/etc/fstab` | Persistent mount configuration |
| `/etc/sysctl.d/99-nfs-tuning.conf` | Kernel tuning |
| `/etc/auto.master`, `/etc/auto.nfs` | Autofs configuration |

