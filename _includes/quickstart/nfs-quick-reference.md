| Task | Command |
|------|---------|
| List NFS mounts | `mount \| grep nfs` |
| Show exports | `showmount -e <server>` |
| Mount NFS | `mount -t nfs4 <server>:<export> <mountpoint>` |
| Unmount NFS | `umount <mountpoint>` |
| NFS statistics | `nfsstat -c` |
| Mount info | `nfsstat -m` |

