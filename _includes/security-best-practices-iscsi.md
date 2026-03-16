# Security Best Practices (iSCSI)

## Network Security

### Dedicated Storage Network

**Why use dedicated storage networks:**
- **Isolation**: Storage traffic cannot be intercepted from management/VM networks
- **Performance**: No bandwidth competition with other traffic
- **Simplicity**: Easier troubleshooting and monitoring

**Implementation:**
- Use separate physical NICs or VLANs for storage traffic
- Isolate at switch level (separate VLANs, ACLs)
- Consider separate physical switches for maximum isolation

### Firewall Configuration

> **⚠️ Recommended**: Disable host-based firewall on dedicated storage interfaces. Network isolation (VLANs, dedicated switches) provides security at the infrastructure layer where it belongs.

**Why disable filtering on storage interfaces:**
- **CPU overhead**: Firewall packet inspection adds latency and consumes CPU cycles
- **Performance impact**: At high IOPS, filtering overhead becomes significant
- **Network isolation**: Dedicated storage VLANs provide security at the network layer
- **Simplicity**: No port rules to maintain for storage traffic

**If filtering is required (e.g., shared network):**

```bash
# Allow only iSCSI traffic on storage interfaces
iptables -A INPUT -i ens1f0 -p tcp --dport 3260 -j ACCEPT  # iSCSI
iptables -A INPUT -i ens1f0 -j DROP  # Drop all other traffic
```

**Required Ports (if using port filtering):**
- **iSCSI**: Port 3260

### Access Control

**Storage Array Configuration:**
- **Register only authorized host identifiers**
  - iSCSI: Initiator IQN
  - FC: WWPN
- **Map volumes only to specific hosts**
- **Use host groups for clustered environments**

**Verify host identifier:**
```bash
# iSCSI: Check initiator IQN
cat /etc/iscsi/initiatorname.iscsi
# Example: InitiatorName=iqn.2004-10.com.ubuntu:01:abc123def456
```

## Authentication

### CHAP Authentication (iSCSI)

**Why use CHAP:**
- Prevents unauthorized initiators from connecting
- Provides mutual authentication (bidirectional CHAP)
- Required in some compliance frameworks

**Configure CHAP:**
```bash
# Edit /etc/iscsi/iscsid.conf
node.session.auth.authmethod = CHAP
node.session.auth.username = <initiator_username>
node.session.auth.password = <initiator_password>

# For mutual (bidirectional) CHAP:
node.session.auth.username_in = <target_username>
node.session.auth.password_in = <target_password>
```

**CHAP best practices:**
- Use unique credentials per initiator
- Rotate passwords periodically
- Store credentials securely
- Use bidirectional CHAP for maximum security

### iSCSI Header Digest

**Enable header and data digests for integrity:**
```bash
# Edit /etc/iscsi/iscsid.conf
node.conn[0].iscsi.HeaderDigest = CRC32C
node.conn[0].iscsi.DataDigest = CRC32C
```

**Note:** Enabling digests adds CPU overhead but ensures data integrity.

## Operating System Hardening

### Kernel Parameters

**Disable unnecessary features:**
```bash
# /etc/sysctl.d/99-storage-security.conf

# Disable source routing
net.ipv4.conf.all.accept_source_route = 0

# Disable ICMP redirects on storage interfaces
net.ipv4.conf.ens1f0.accept_redirects = 0
net.ipv4.conf.ens1f1.accept_redirects = 0

# Enable reverse path filtering
net.ipv4.conf.ens1f0.rp_filter = 1
net.ipv4.conf.ens1f1.rp_filter = 1
```

### Service Hardening

**Limit iSCSI service exposure:**
```bash
# Bind iscsid to storage interfaces only
# In /etc/iscsi/iscsid.conf (if supported):
# iface.net_ifacename = ens1f0
```

## Audit and Compliance

### Logging

**Enable detailed logging:**
```bash
# iSCSI logging
echo "module iscsi_tcp +p" > /sys/kernel/debug/dynamic_debug/control

# Monitor authentication failures
journalctl -u iscsid | grep -i "auth\|chap\|login"
```

### Regular Security Review

**Checklist:**
- [ ] Review storage array access lists quarterly
- [ ] Rotate CHAP credentials annually
- [ ] Audit network ACLs and VLAN configurations
- [ ] Test failover procedures semi-annually
- [ ] Review and update firewall rules as needed

