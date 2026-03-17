### Understanding LACP Load Balancing

LACP uses hash-based distribution—there's no guarantee of balanced traffic:

- Each flow (source/dest IP+port) uses a single link
- Single NFS mount may use only one link
- Use `nconnect` to create multiple TCP connections that may hash to different links

