> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

## Security Best Practices

### Network Security

#### 1. Network Isolation

**Dedicated Storage Network:**
- **Never route storage traffic through management network**
  - *Why*: Prevents unauthorized access to storage traffic; reduces attack surface; improves performance
- **Use dedicated VLANs or physical networks for storage**
  - *Why*: Isolates storage from other network traffic; prevents VLAN hopping attacks
- **No default gateway on storage interfaces**
  - *Why*: Prevents routing storage traffic outside the storage network; reduces exposure

**Configuration:**
```bash
# Storage interfaces should NOT have gateway configured
# /etc/network/interfaces
auto ens1f0
iface ens1f0 inet static
    address 10.100.1.101/24
    mtu 9000
    # NO gateway line
```

**Verification:**
```bash
# Verify no default route on storage interface
ip route show dev ens1f0
# Should show only local subnet route
```

#### 2. Firewall Configuration

**Option 1: Disable Filtering on Storage Interfaces (Recommended)**

For dedicated, isolated storage networks, **disable firewall filtering** on storage interfaces to eliminate CPU overhead from packet inspection.

```bash
# Add storage interfaces to trusted zone (firewalld)
firewall-cmd --permanent --zone=trusted --add-interface=ens1f0
firewall-cmd --permanent --zone=trusted --add-interface=ens1f1
firewall-cmd --reload

# Or accept all traffic on interfaces (iptables)
iptables -A INPUT -i ens1f0 -j ACCEPT
iptables -A INPUT -i ens1f1 -j ACCEPT
```

**Why disable filtering on storage interfaces:**
- **CPU overhead**: Firewall packet inspection adds latency and consumes CPU cycles
- **Performance impact**: At high IOPS (millions with NVMe-TCP), filtering overhead becomes significant
- **Network isolation**: Dedicated storage VLANs provide security at the network layer
- **Simplicity**: No port rules to maintain for storage traffic

**Option 2: Port Filtering (For Shared or Non-Isolated Networks)**

Use port filtering only when storage interfaces share a network with other traffic or when additional host-level security is required by policy.

> **⚠️ Performance Note:** Port filtering adds CPU overhead for every packet. For production storage with high IOPS requirements, use Option 1 with network-level isolation instead.

```bash
# Allow only NVMe-TCP traffic on storage interfaces
# Port 4420 = Data port (connections)
# Port 8009 = Discovery port (optional)
iptables -A INPUT -i ens1f0 -p tcp --dport 4420 -j ACCEPT
iptables -A INPUT -i ens1f0 -p tcp --dport 8009 -j ACCEPT
iptables -A INPUT -i ens1f0 -j DROP  # Drop all other traffic
```

**Required Ports (if using port filtering):**
- **NVMe-TCP**: Port 4420 (data), Port 8009 (discovery)

#### 3. Access Control

**Storage Array Configuration:**
- **Register only authorized Host NQNs**
- **Implement IP-based ACLs on storage array**
- **Regularly audit authorized hosts**

**Verify host identifier:**
```bash
# Check host NQN
cat /etc/nvme/hostnqn
# Example: nqn.2014-08.org.nvmexpress:uuid:12345678-1234-1234-1234-123456789abc
```

**Best Practice:**
- Use unique NQN per host (don't clone VMs without regenerating)
- Document all registered NQNs
- Remove decommissioned hosts from storage array

### Authentication and Encryption

#### TLS Encryption (NVMe-TCP)

**NVMe-TCP with TLS (if supported):**

**Why use TLS:**
- Encrypts data in transit
- Prevents eavesdropping on storage traffic
- Required for compliance in some industries

**Configuration:**
```bash
# Connect with TLS (requires kernel 5.15+ and array support)
nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn> \
    --tls
```

**Considerations:**
- Performance impact: 5-15% throughput reduction
- CPU overhead: Encryption/decryption uses CPU cycles
- Certificate management: Requires PKI infrastructure
- Only use if required by security policy or compliance

#### DH-HMAC-CHAP Authentication

**NVMe-oF supports DH-HMAC-CHAP authentication (kernel 5.16+):**
```bash
# Configure host authentication key
nvme gen-dhchap-key -n <subsystem_nqn> > /etc/nvme/hostkey

# Connect with authentication
nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn> \
    --dhchap-secret=/etc/nvme/hostkey
```

**Note:** Array must also be configured for DH-HMAC-CHAP. Check vendor documentation.

### Host Security

#### 1. Minimize Attack Surface

**Disable unnecessary services:**
```bash
# List running services
systemctl list-units --type=service --state=running

# Disable unnecessary services
systemctl disable <service_name>
systemctl stop <service_name>
```

#### 2. Keep Systems Updated

**Regular patching:**
```bash
# RHEL/Rocky/AlmaLinux
dnf update

# Debian/Ubuntu
apt update && apt upgrade

# SUSE
zypper update
```

**Best Practices:**
- Patch monthly at minimum
- Test patches in non-production first
- Have rollback plan
- Monitor security advisories for NVMe/kernel updates

#### 3. Audit and Logging

**Enable audit logging:**
```bash
# Install and enable auditd
systemctl enable --now auditd

# Add audit rules for NVMe devices
auditctl -w /dev/nvme0n1 -p rwa -k nvme_access
auditctl -w /etc/nvme/ -p wa -k nvme_config
```

