---
layout: default
title: iSCSI on XCP-ng - GUI Quick Start Guide (Xen Orchestra)
---

# iSCSI on XCP-ng - GUI Quick Start Guide

This guide walks you through configuring iSCSI storage on XCP-ng using **Xen Orchestra (XO)** web interface with multipathing enabled.

> **📘 For CLI-based setup:** See [iSCSI Quick Start (CLI)](./QUICKSTART.md)
> **📘 For production best practices:** See [iSCSI Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- XCP-ng 8.2 or later with Xen Orchestra installed
- iSCSI storage array with:
  - Portal IPs (at least 2 for multipathing)
  - Target IQN
  - LUN/Volume created and mapped to XCP-ng hosts
- Dedicated storage network interfaces configured
- CHAP credentials (if required by your storage array)

{% include quickstart/glossary-link-iscsi.md %}

---

## Step 1: Configure Storage Network (All Hosts)

Before adding iSCSI storage, ensure your storage network interfaces are configured on each host.

### Via Xen Orchestra

1. Navigate to **Home → Hosts** and select your host
2. Go to the **Network** tab
3. Identify your storage interfaces

<!-- TODO: Add screenshot of XO Host Network tab -->
> **📸 Screenshot placeholder:** _XO Host Network tab showing storage interfaces_

4. If needed, configure static IPs on storage interfaces via **Network → PIFs**

### Via XCP-ng Center (Alternative)

1. Open XCP-ng Center and connect to your pool
2. Select a host → **Networking** tab
3. Configure storage interfaces with static IPs

<!-- TODO: Add screenshot of XCP-ng Center Networking tab -->
> **📸 Screenshot placeholder:** _XCP-ng Center Networking configuration_

---

## Step 2: Enable Multipathing on Pool

Multipathing must be enabled at the pool level before adding iSCSI storage.

### Via Xen Orchestra

1. Navigate to **Home → Pools** and select your pool
2. Go to the **Advanced** tab
3. Find **Multipathing** and enable it

<!-- TODO: Add screenshot of XO Pool Advanced tab with Multipathing option -->
> **📸 Screenshot placeholder:** _XO Pool Advanced tab - Multipathing toggle_

4. Click **Save** or apply the changes

### Via CLI (Alternative)

If XO doesn't show the multipathing option, use CLI on the pool master:

```bash
# Enable multipathing for the pool
xe host-param-set uuid=<HOST_UUID> other-config:multipathing=true
xe host-param-set uuid=<HOST_UUID> other-config:multipathhandle=dmp
```

---

## Step 3: Configure Custom Multipath Settings (Optional)

For optimal performance with your storage array, configure custom multipath settings.

### Via SSH to Each Host

```bash
# Create custom multipath configuration
cat > /etc/multipath/conf.d/custom.conf << 'EOF'
devices {
    device {
        vendor           "PURE"
        product          "FlashArray"
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

# Restart multipathd
systemctl restart multipathd
```

> **Note:** Adjust the `vendor` and `product` values to match your storage array.

---

## Step 4: Add iSCSI Storage Repository

### Via Xen Orchestra

1. Click **New → Storage** in the top menu

<!-- TODO: Add screenshot of XO New Storage menu -->
> **📸 Screenshot placeholder:** _XO New Storage dropdown menu_

2. Select **iSCSI** as the storage type

<!-- TODO: Add screenshot of storage type selection -->
> **📸 Screenshot placeholder:** _Storage type selection showing iSCSI option_

3. Fill in the iSCSI connection details:

| Field | Value | Description |
|-------|-------|-------------|
| **Name** | `Pure-iSCSI-SR` | Descriptive name for the SR |
| **Description** | `Pure FlashArray iSCSI` | Optional description |
| **Host** | Select pool master | Initial host for discovery |
| **Target IPs** | `10.100.1.10,10.100.1.11` | Comma-separated portal IPs |
| **Port** | `3260` | iSCSI port (default: 3260) |

<!-- TODO: Add screenshot of iSCSI connection form -->
> **📸 Screenshot placeholder:** _iSCSI SR creation form - connection details_

4. Click **Discover IQNs** or **Connect**

5. Select the target IQN from the dropdown

<!-- TODO: Add screenshot showing IQN selection -->
> **📸 Screenshot placeholder:** _Target IQN dropdown selection_

6. Select the LUN to use

<!-- TODO: Add screenshot showing LUN selection -->
> **📸 Screenshot placeholder:** _LUN selection for SR creation_

7. If CHAP is required, enter credentials:
   - **Username:** Your CHAP username
   - **Password:** Your CHAP secret

<!-- TODO: Add screenshot of CHAP authentication fields -->
> **📸 Screenshot placeholder:** _CHAP authentication fields_

8. Click **Create**

<!-- TODO: Add screenshot of SR creation success -->
> **📸 Screenshot placeholder:** _SR creation success message_

---

## Step 5: Verify Storage Repository

### Via Xen Orchestra

1. Navigate to **Home → SRs** (Storage Repositories)
2. Find your new iSCSI SR in the list
3. Click on it to view details

<!-- TODO: Add screenshot of SR list -->
> **📸 Screenshot placeholder:** _SR list showing new iSCSI SR_

4. Verify the SR shows:
   - **Status:** Connected (green)
   - **Type:** lvmoiscsi
   - **Shared:** Yes (available on all hosts)

<!-- TODO: Add screenshot of SR details page -->
> **📸 Screenshot placeholder:** _SR details page showing status and configuration_

---

## Step 6: Verify Multipathing

### Via Xen Orchestra

1. In the SR details, check the **Physical Block Devices (PBDs)** section
2. Each host should show "connected" status

<!-- TODO: Add screenshot of PBD connections -->
> **📸 Screenshot placeholder:** _PBD connections showing all hosts connected_

### Via SSH (Verification)

Connect to each host via SSH and verify multipath:

```bash
# Check multipath status
multipath -ll

# Expected output showing multiple paths:
# 3600... dm-X VENDOR,PRODUCT
# size=100G features='0' hwhandler='1 alua' wp=rw
# |-+- policy='service-time 0' prio=50 status=active
# | |- 1:0:0:1 sda 8:0   active ready running
# | `- 2:0:0:1 sdb 8:16  active ready running
# `-+- policy='service-time 0' prio=10 status=enabled
#   |- 3:0:0:1 sdc 8:32  active ready running
#   `- 4:0:0:1 sdd 8:48  active ready running
```

<!-- TODO: Add screenshot of multipath -ll output -->
> **📸 Screenshot placeholder:** _Terminal showing multipath -ll output with multiple active paths_

---

## Step 7: Create a Test VM

### Via Xen Orchestra

1. Click **New → VM**
2. Select your template (e.g., Ubuntu, CentOS)
3. In the **Disks** section, select your new iSCSI SR

<!-- TODO: Add screenshot of VM creation disk selection -->
> **📸 Screenshot placeholder:** _VM creation showing iSCSI SR selected for disk storage_

4. Complete the VM creation wizard
5. Start the VM and verify it runs correctly

---

## Troubleshooting

### SR Not Connecting

1. **Check network connectivity:**
   ```bash
   ping 10.100.1.10  # Your portal IP
   nc -zv 10.100.1.10 3260  # Test iSCSI port
   ```

2. **Check multipath service:**
   ```bash
   systemctl status multipathd
   ```

3. **View logs in XO:**
   - Navigate to **Home → Logs**
   - Filter for storage-related events

<!-- TODO: Add screenshot of XO Logs page -->
> **📸 Screenshot placeholder:** _XO Logs page showing storage events_

### Paths Showing Failed

1. **Check path status:**
   ```bash
   multipath -ll | grep -E "status|failed"
   ```

2. **Reinstate paths:**
   ```bash
   multipathd show paths
   multipathd reinstate path <device>
   ```

3. **Restart multipath:**
   ```bash
   systemctl restart multipathd
   ```

---

## Quick Reference

| Task | Xen Orchestra Location |
|------|----------------------|
| View SRs | Home → SRs |
| Pool Settings | Home → Pools → Advanced |
| Host Network | Home → Hosts → [Host] → Network |
| Logs | Home → Logs |
| Create VM | New → VM |

### CLI Commands

```bash
# List SRs
xe sr-list

# Check SR status
xe sr-list name-label="Pure-iSCSI-SR"

# Verify multipath
multipath -ll

# Check PBD connections
xe pbd-list sr-uuid=<SR_UUID>
```

---

## Next Steps

- [iSCSI Best Practices](./BEST-PRACTICES.md) - Production deployment guidance
- [iSCSI CLI Quick Start](./QUICKSTART.md) - Command-line configuration
- [NFS Quick Start](../nfs/QUICKSTART.md) - Alternative storage protocol
- [Common Troubleshooting]({{ site.baseurl }}/common/troubleshooting-common.html)

