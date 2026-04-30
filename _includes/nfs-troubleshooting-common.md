### Common Issues

| Issue | Solution |
|-------|----------|
| Mount fails | Check `showmount -e <server>`, verify firewall |
| Stale handle | Force unmount: `umount -f <mount>` |
| Slow performance | Verify nconnect, check network throughput |
| Permission denied | Check export permissions, root_squash settings |

### Diagnostic Commands

```bash
# NFS statistics
nfsstat -c
nfsstat -m

# Check RPC services
rpcinfo -p <NFS_SERVER_IP>

# Test connectivity
showmount -e <NFS_SERVER_IP>
```

