### Mount Fails

```bash
# Check network connectivity
ping <NFS_SERVER_IP>
nc -zv <NFS_SERVER_IP> 2049

# Check exports
showmount -e <NFS_SERVER_IP>
```

### Performance Issues

```bash
# Check NFS version and options
nfsstat -m

# Verify nconnect
cat /proc/fs/nfsfs/servers
```

