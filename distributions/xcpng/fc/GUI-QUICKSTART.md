---
layout: default
title: Fibre Channel on XCP-ng - GUI Quick Start Guide (Xen Orchestra)
---

# Fibre Channel on XCP-ng - GUI Quick Start Guide

This guide walks you through configuring Fibre Channel storage on XCP-ng using the **Xen Orchestra (XO)** web interface.

> **📘 For CLI-based setup:** See [FC Quick Start (CLI)](./QUICKSTART.md)
> **📘 For production best practices:** See [FC Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.3 or later with Xen Orchestra installed
- Fibre Channel HBA installed in each pool host and cabled to the FC fabric
- Fabric zoning and volume presentation configured by your SAN administrator
  - All pool host WWPNs registered on the FlashArray and added to a host group
  - Volume connected to the host group

{% include quickstart/glossary-link-fc.md %}

---

## Step 1: Verify HBA and Collect WWPNs (CLI — All Hosts)

Before working in Xen Orchestra, verify that all HBA ports are online and collect WWPNs for registration on the array. Run on **every pool host**:

{% include quickstart/fc-hba-verify.md %}

> **Note:** Once the hosts are zoned to the fabric, the FlashArray can often auto-discover their WWPNs. When creating the host on the Pure side, the connected WWPNs appear in a selectable list — letting you add them directly rather than copying each one from the host CLI. As long as fabric connectivity is established, this may let you skip the manual collection step above.

---

## Step 2: Register WWPNs and Present Volume (Array Side)

{% include quickstart/fc-zoning-checklist.md %}

---

## Step 3: Enable Multipathing on Pool (Xen Orchestra)

1. Log in to Xen Orchestra
2. Navigate to your **Pool** → **Advanced** tab
3. Enable **Multipathing for all XCP-ng hosts**

> If the Advanced tab does not show a multipathing toggle, enable it via `xe` CLI instead:
> ```bash
> xe host-list   # get host UUIDs
> xe host-param-set uuid=<HOST_UUID> other-config:multipathing=true
> xe host-param-set uuid=<HOST_UUID> other-config:multipathhandle=dmp
> ```

---

## Step 4: Configure Custom Multipath Entry (CLI — If Required)

Check whether your array is already defined in XCP-ng's default multipath configuration:

```bash
cat /etc/multipath.xenserver/multipath.conf | grep -i "PURE"
```

If not present, add a custom entry (run on **every pool host**):

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

---

## Step 5: Create FC Storage Repository (Xen Orchestra)

1. In Xen Orchestra, click **New → Storage**
2. Select the **master host** in your pool
3. Select **HBA** as the storage type
4. Enter a name for the storage repository (e.g., `FC Storage — FlashArray`)
5. In the device list, select the LUN presented from the FlashArray (identified by its WWID / SCSIid)

![Create FC Storage Repository — select the LVM (HBA) device](images/FC%20Setup%20Step%201.png)

6. Choose the disk image format for the SR — select **VHD** for broad compatibility with existing tooling, or **QCOW2** for support of larger virtual disks and more efficient thin provisioning. Choose the format that best fits your needs.

![Choosing the disk image format (VHD or QCOW2) for the Storage Repository](images/FC%20Setup%20Step%202.png)

7. Click **Create**

> **Tip:** If the expected LUN does not appear, verify that `multipath -ll` shows the FC device on **all pool hosts**, and that the volume is connected to the correct host group on the FlashArray.

---

## Step 6: Verify

In Xen Orchestra:

1. Navigate to **Storage** in the left sidebar
2. Confirm the new SR appears and its status shows as connected
3. Check that **all hosts in the pool** show as connected to the SR

![Verifying the FC Storage Repository in Xen Orchestra](images/FC%20Setup%20Step%203.png)

Via CLI, confirm on each host:

```bash
# Check SR status
xe sr-list name-label="FC Storage"
xe pbd-list sr-uuid=<SR_UUID>

# Check multipath
multipath -ll

# Check HBA state
cat /sys/class/fc_host/host*/port_state
```

---

{% include quickstart/fc-quick-reference.md %}
