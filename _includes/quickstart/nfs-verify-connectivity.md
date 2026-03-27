```bash
# Test connectivity to NFS server
ping -c 3 <NFS_SERVER_IP>

# Test NFS port (2049) - use one of these methods:
# Method 1: Using bash (works on all distributions)
timeout 3 bash -c '</dev/tcp/<NFS_SERVER_IP>/2049' && echo "NFS port 2049 is open"

# Method 2: Using nc (may require installation)
# Debian/Ubuntu: apt install netcat-openbsd
# RHEL/Rocky/Oracle: dnf install nmap-ncat
# SUSE: zypper install netcat-openbsd
nc -zv <NFS_SERVER_IP> 2049

# List available exports (optional - may not be available on all distributions)
# Debian: included with nfs-common
# RHEL/Rocky/Oracle: included with nfs-utils
# SUSE: not available by default
showmount -e <NFS_SERVER_IP>
```
