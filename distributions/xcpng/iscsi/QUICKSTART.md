---
layout: default
title: iSCSI on XCP-ng - Quick Start Guide
---

# iSCSI on XCP-ng - Quick Start Guide

This guide provides a streamlined path to configure iSCSI storage on XCP-ng.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [XCP-ng Storage Documentation](https://docs.xcp-ng.org/storage/)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.2 or later
- iSCSI storage array with portal IPs and target IQN
- Dedicated storage network interfaces (recommended: separate NICs/VLANs)
- Root access to all pool hosts

{% include quickstart/glossary-link-iscsi.md %}

{% include quickstart/arp-warning.md %}

## Step 1: Configure Storage Network Interfaces

Configure dedicated network interfaces for iSCSI traffic using Xen Orchestra or xe CLI. Replace `<PIF_UUID>` with your physical interface UUID and configure appropriate IP addressing.

```bash
# List available PIFs
xe pif-list

# Configure static IP on storage interface (example)
xe pif-reconfigure-ip uuid=<PIF_UUID> mode=static IP=<HOST_IP> netmask=<NETMASK>

# Verify interface configuration
xe pif-list params=uuid,device,IP,netmask
```

> **Tip:** Use `xe pif-list` to identify your storage interfaces. Dedicated NICs for iSCSI traffic provide better performance and isolation.

## Step 2: Verify iSCSI and Multipath Tools

XCP-ng includes iSCSI and multipath tools by default. Verify they are available:

```bash
# Verify iscsi-initiator-utils is installed
rpm -qa | grep iscsi-initiator-utils

# Verify multipath tools
rpm -qa | grep device-mapper-multipath

# Enable and start services
systemctl enable --now iscsid multipathd
```

## Step 3: Configure Multipath (If Required)

If your storage equipment is not already in the default multipath configuration, add custom settings:

```bash
# Check if your storage is already configured
cat /etc/multipath.xenserver/multipath.conf | grep -i "<VENDOR>"

# If not present, create custom configuration
cat >> /etc/multipath/conf.d/custom.conf << 'EOF'
devices {
    device {
        vendor           "<VENDOR>"
        product          "<PRODUCT>"
        path_selector    "service-time 0"
        path_grouping_policy group_by_prio
        prio             alua
        hardware_handler "1 alua"
        failback         immediate
        rr_weight        uniform
        no_path_retry    0
    }
}
EOF

# Restart multipathd to apply
systemctl restart multipathd
```

> **Note:** Configuration in `/etc/multipath/conf.d/custom.conf` persists across updates. Never modify `/etc/multipath.xenserver/multipath.conf` directly.

## Step 4: Enable Pool Multipathing

Enable multipathing at the pool level via Xen Orchestra or xe CLI:

```bash
# Via xe CLI - enable on pool
xe host-param-set uuid=<HOST_UUID> other-config:multipathing=true
xe host-param-set uuid=<HOST_UUID> other-config:multipathhandle=dmp
```

> **Tip:** In Xen Orchestra, go to Pool → Advanced tab and enable "Multipathing for all XCP-ng hosts".

## Step 5: Create iSCSI Storage Repository

Create the iSCSI SR using Xen Orchestra (recommended) or xe CLI:

### Via Xen Orchestra (Recommended)

1. Go to **New → Storage**
2. Select **iSCSI** as storage type
3. Enter portal IPs, target IQN, and authentication details
4. Select the LUN to use
5. Click **Create**

### Via xe CLI

```bash
# Discover targets
iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_1>:3260
iscsiadm -m discovery -t sendtargets -p <PORTAL_IP_2>:3260

# Create iSCSI SR (lvmoiscsi driver)
xe sr-create name-label="iSCSI Storage" type=lvmoiscsi shared=true \
    device-config:target=<PORTAL_IP_1>,<PORTAL_IP_2> \
    device-config:targetIQN=<TARGET_IQN> \
    device-config:SCSIid=<SCSI_ID>
```

> **Note:** The `SCSIid` can be found using `iscsiadm -m session -P 3` after a manual login, or via your storage array's management interface.

## Step 6: Verify Configuration

```bash
# Verify iSCSI sessions
iscsiadm -m session

# Verify multipath devices
multipath -ll

# Verify SR status in XCP-ng
xe sr-list type=lvmoiscsi
xe pbd-list sr-uuid=<SR_UUID>
```

---

{% include quickstart/iscsi-quick-reference.md %}

## Next Steps

For production deployments, consult the official XCP-ng documentation:
- [XCP-ng Storage Documentation](https://docs.xcp-ng.org/storage/)
- [XCP-ng Multipathing Guide](https://docs.xcp-ng.org/storage/multipathing)
- [XCP-ng Networking](https://docs.xcp-ng.org/networking/)

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

