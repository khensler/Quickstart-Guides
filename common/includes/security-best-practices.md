---

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use. In case of conflicts, vendor documentation takes precedence.

---

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

#### 2. Firewall Rules

**Restrict storage network access:**

```bash
# Allow only storage traffic on storage interfaces
# Example for iptables
iptables -A INPUT -i ens1f0 -p tcp --dport 4420 -j ACCEPT  # NVMe-TCP
iptables -A INPUT -i ens1f0 -p tcp --dport 3260 -j ACCEPT  # iSCSI
iptables -A INPUT -i ens1f0 -j DROP  # Drop all other traffic
```

**Best Practices:**
- Only allow required ports (NVMe-TCP: 4420, iSCSI: 3260)
- Drop all other traffic on storage interfaces
- Log dropped packets for security monitoring

#### 3. Access Control

**Storage Array Configuration:**
- **Register only authorized host identifiers**
  - NVMe-TCP: Host NQN
  - iSCSI: Initiator IQN
  - FC: WWPN
- **Use CHAP authentication if supported** (iSCSI)
- **Implement IP-based ACLs on storage array**
- **Regularly audit authorized hosts**

**Verify host identifier:**
```bash
# NVMe-TCP: Check host NQN
cat /etc/nvme/hostnqn
# Example: nqn.2014-08.org.nvmexpress:uuid:12345678-1234-1234-1234-123456789abc

# iSCSI: Check initiator IQN
cat /etc/iscsi/initiatorname.iscsi
# Example: iqn.1993-08.org.debian:01:abcdef123456
```

**Best Practice:**
- Use unique identifiers per host (don't clone)
- Document all registered identifiers
- Remove decommissioned hosts from storage array

### Authentication and Encryption

#### CHAP Authentication (iSCSI)

**Why use CHAP:**
- Prevents unauthorized initiators from accessing storage
- Adds authentication layer beyond IP-based ACLs
- Industry best practice for iSCSI security

**Configuration:**
```bash
# Configure CHAP on initiator
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.auth.authmethod -v CHAP
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.auth.username -v <username>
iscsiadm -m node -T <target_iqn> -p <portal_ip> \
    -o update -n node.session.auth.password -v <password>
```

**Best Practices:**
- Use strong passwords (16+ characters)
- Rotate passwords regularly
- Use mutual CHAP for bidirectional authentication
- Store credentials securely

#### TLS/Encryption (NVMe-TCP)

**NVMe-TCP with TLS (if supported):**

**Why use TLS:**
- Encrypts data in transit
- Prevents eavesdropping on storage traffic
- Required for compliance in some industries

**Configuration:**
```bash
# Connect with TLS (requires kernel 5.15+)
nvme connect -t tcp -a <portal_ip> -s 4420 -n <subsystem_nqn> \
    --tls
```

**Considerations:**
- Performance impact: 5-15% throughput reduction
- CPU overhead: Encryption/decryption uses CPU cycles
- Certificate management: Requires PKI infrastructure
- Only use if required by security policy or compliance

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

**Remove unnecessary packages:**
```bash
# Audit installed packages
dpkg -l | less  # Debian/Ubuntu
rpm -qa | less  # RHEL/SUSE

# Remove unnecessary packages
apt remove <package>  # Debian/Ubuntu
dnf remove <package>  # RHEL
zypper remove <package>  # SUSE
```

#### 2. Keep Systems Updated

**Regular patching:**
```bash
# Debian/Ubuntu
apt update && apt upgrade

# RHEL
dnf update

# SUSE
zypper update
```

**Best Practices:**
- Patch monthly at minimum
- Test patches in non-production first
- Have rollback plan
- Monitor security advisories

#### 3. Audit and Logging

**Enable audit logging:**
```bash
# Install auditd
apt install auditd  # Debian/Ubuntu
dnf install audit  # RHEL
zypper install audit  # SUSE

# Enable and start
systemctl enable --now auditd
```

**Monitor storage access:**
```bash
# Add audit rules for storage devices
auditctl -w /dev/mapper/ -p rwa -k storage_access

# View audit logs
ausearch -k storage_access
```

**Centralized logging:**
- Forward logs to SIEM or log aggregator
- Monitor for suspicious activity
- Retain logs per compliance requirements

### Compliance Considerations

**Common requirements:**
- **Encryption at rest**: Configure on storage array
- **Encryption in transit**: Use TLS/IPsec if required
- **Access logging**: Enable audit logging
- **Multi-factor authentication**: For management access
- **Regular security audits**: Quarterly or per policy
- **Vulnerability scanning**: Regular scans of infrastructure
- **Incident response plan**: Document and test procedures

**Documentation:**
- Maintain network diagrams
- Document all access controls
- Keep audit trail of changes
- Regular security reviews

