---
layout: default
title: Fibre Channel on XCP-ng - Quick Start Guide
---

# Fibre Channel on XCP-ng - Quick Start Guide

This guide provides a streamlined path to configure Fibre Channel storage on XCP-ng using the `xe` CLI.

> **📘 For GUI-based setup with Xen Orchestra:** See [FC GUI Quick Start](./GUI-QUICKSTART.md)
> **📘 For detailed explanations and troubleshooting:** See [XCP-ng Storage Documentation](https://docs.xcp-ng.org/storage/)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.3 or later
- Fibre Channel HBA installed in each pool host and cabled to the FC fabric
- Fabric zoning and volume presentation configured by your SAN administrator
- Root access to all pool hosts

{% include quickstart/glossary-link-fc.md %}

---

## Step 1: Verify HBA and Collect WWPNs

Run on **every pool host**:

{% include quickstart/fc-hba-verify.md %}

> **Collect WWPNs from all pool hosts** before proceeding — every host must be registered on the array.

## Step 2: Register WWPNs and Present Volume

{% include quickstart/fc-zoning-checklist.md %}

## Step 3: Configure Multipath (If Required)

XCP-ng ships a default multipath configuration. Check whether your storage array is already defined:

```bash
cat /etc/multipath.xenserver/multipath.conf | grep -i "PURE"
```

If not present, add a custom device entry:

```bash
cat >> /etc/multipath/conf.d/custom.conf << 'EOF'
devices {
    device {
        vendor               "PURE"
        product              "FlashArray"
        path_selector        "service-time 0"
        hardware_handler     "1 alua"
        path_grouping_policy group_by_prio
        prio                 alua
        failback             immediate
        no_path_retry        0
        fast_io_fail_tmo     5
        dev_loss_tmo         60
    }
}
EOF

systemctl restart multipathd
```

> **Never modify `/etc/multipath.xenserver/multipath.conf` directly** — always write custom entries to `/etc/multipath/conf.d/custom.conf` so they persist across updates.

## Step 4: Enable Pool Multipathing

```bash
# Enable multipathing on each host — replace <HOST_UUID> with your host UUID
xe host-list          # get host UUIDs
xe host-param-set uuid=<HOST_UUID> other-config:multipathing=true
xe host-param-set uuid=<HOST_UUID> other-config:multipathhandle=dmp
```

## Step 5: Create an FC Storage Repository

XCP-ng uses the `lvmohba` SR type for Fibre Channel block storage:

```bash
# Probe for available FC devices — shows SCSIids for visible LUNs
xe sr-probe type=lvmohba

# Create the SR using the SCSIid from the probe output
xe sr-create name-label="FC Storage" type=lvmohba shared=true \
    device-config:SCSIid=<SCSI_ID>
```

> The `SCSIid` is the WWID of the LUN — the same identifier shown in `multipath -ll`. Confirm the SCSIid matches the expected device before creating the SR.

## Step 6: Verify

```bash
# Check HBA port state
cat /sys/class/fc_host/host*/port_state

# Check multipath
multipath -ll

# Verify SR is accessible on all hosts
xe sr-list name-label="FC Storage"
xe pbd-list sr-uuid=<SR_UUID>
```

---

{% include quickstart/fc-quick-reference.md %}

---

## Next Steps

For production deployments, see the [XCP-ng Storage Documentation](https://docs.xcp-ng.org/storage/) and [FC Best Practices](./BEST-PRACTICES.md) for:
- Fabric redundancy and HBA driver notes
- Multipath configuration details
- Monitoring and troubleshooting

**Additional Resources:**
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)
