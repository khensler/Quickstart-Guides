---
layout: default
title: Platform9 PCD - Pure Storage FlashArray Fibre Channel Integration Guide
---

# Platform9 Private Cloud Director — Pure Storage FlashArray Fibre Channel Integration

This guide covers the complete process of integrating Pure Storage FlashArray with Platform9 Private Cloud Director (PCD) using Fibre Channel and DM-Multipath. Substitute all placeholder values (shown in `<ANGLE_BRACKETS>`) with your environment's actual values.

> **📘 Note:** Many configuration steps are performed in the PCD UI. This guide assumes PCD is already deployed and your hypervisor nodes are running Ubuntu 24.04 and are reachable from the PCD controller.

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Platform9 PCD environment deployed and accessible
- Pure Storage FlashArray with:
  - Management IP reachable from PCD and hypervisors
  - API token generated
  - FC ports configured and cabled to the fabric
- Two or more hypervisor nodes running **Ubuntu 24.04** with FC HBAs installed
- FC fabric zoning configured — all hypervisor node WWPNs zoned to the array's FC target ports
- SSH access to each hypervisor node

{% include quickstart/glossary-link-fc.md %}

---

## Step 1: Create a Cluster Blueprint

The Cluster Blueprint defines the network, storage, and host configuration for your PCD cluster. This is configured once and applied when you create the cluster.

### 1.1 Navigate to Cluster Blueprint

1. Log in to the PCD UI: `https://<PCD_MANAGEMENT_URL>`
2. Navigate to **Infrastructure > Cluster Blueprint**
3. Click **+ New Blueprint** and name it (e.g., `pcd-pure-fc-blueprint`)

### 1.2 Configure Network Segmentation

PCD supports three segmentation technologies. Select the one that matches your network design:

| Option | Description | Best For |
|--------|-------------|----------|
| **VLAN Underlay** | Traditional VLAN-based segmentation | Environments with managed switches |
| **IP Underlay for VXLAN Overlay** | Overlay network (up to 16M segments) | Scalable multi-tenant environments |
| **IP Underlay for GENEVE Overlay** | Flexible overlay, no VLAN config required | Nested virtualization, lab environments |

### 1.3 Configure Host Network Interfaces

Under **Host Configuration**, add an entry (e.g., `default-hypervisor`) and map your management interface:

- **Interface:** `eth0` (or the interface carrying management traffic)
- **Physical Network Label:** `physnet1`
- **Traffic Types:** Management, VM Console, Image Library I/O, Virtual Network Tunnels, Host Liveness Checks

> **Fibre Channel note:** FC storage traffic does not flow over IP interfaces and does not require a network interface mapping in the PCD blueprint. FC connectivity is established at the HBA/fabric layer outside of PCD's network configuration.

### 1.4 Configure Pure Storage FC Backend

Navigate to **Persistent Storage Connectivity** in the blueprint.

1. Click **+ Add Volume Backend** → Name it `pure-flasharray-fc`
2. Click **+ Add Configuration** → Name it `pure-flasharray-fc-backend`
3. Select the storage driver:

**Driver:** `Pure Storage FC`

4. Configure the key-value pairs:

| Key | Value | Description |
|-----|-------|-------------|
| `san_ip` | `<PURE_STORAGE_IP>` | FlashArray management IP |
| `pure_api_token` | `<PURE_API_TOKEN>` | API authentication token |
| `use_multipath_for_image_xfer` | `true` | **Required** — enables multipath for image transfers |
| `image_volume_cache_enabled` | `true` | Enable image volume caching |
| `image_volume_cache_max_count` | `50` | Maximum cached images |
| `image_volume_cache_max_size_gb` | `200` | Maximum cache size (GB) |
| `volumes_dir` | `/opt/pf9/etc/pf9-cindervolume-base/volumes/` | Volume storage directory |

> **Note:** The FC driver discovers the FlashArray via the management IP (`san_ip`); no portal or CIDR settings are required. The driver reads each hypervisor's WWPNs and registers the host on the array automatically when the first volume is attached. `use_multipath_for_image_xfer` must be `true`.

5. Click **Save Blueprint**

---

## Step 2: Create a Cluster and Authorize Hosts

### 2.1 Create the Cluster

1. Navigate to **Infrastructure > Clusters**
2. Click **+ Add Cluster**
3. Enter a cluster name (e.g., `pcd-pure-fc-cluster`) and click **Add Cluster**

### 2.2 Authorize Hypervisors

Navigate to **Infrastructure > Cluster Hosts**. For **each** hypervisor:

1. Click the hypervisor name
2. Click **Edit Roles**
3. Configure:
   - **Host Config:** `default-hypervisor`
   - **Enable Roles:**
     - ✅ **Hypervisor** — required to run VMs
     - ✅ **Persistent Storage** — required to attach Pure Storage volumes
     - ✅ **Image Library** — required on at least one host to serve Glance images
   - **Assign to Cluster:** `pcd-pure-fc-cluster`
4. Click **Update**

Repeat for all hypervisor nodes.

> **Production note:** The **Image Library** role needs to be enabled on at least one host. For production, use a shared image backend (NFS or Pure Storage-backed Glance) rather than local image storage on a single hypervisor.

---

## Step 3: Configure Multipath on Hypervisors

DM-Multipath must be configured on every hypervisor before Pure Storage volumes can be attached via FC. Perform these steps on **all** hypervisor nodes.

### 3.1 Install Required Packages

```bash
sudo apt-get update
sudo apt-get install -y multipath-tools sg3-utils sysfsutils
```

> **Note:** Only `multipath-tools` and supporting utilities are required for FC. `open-iscsi` and `iscsid` are not used.

### 3.2 Verify HBA and Collect WWPNs

{% include quickstart/fc-hba-verify.md %}

> Provide these WWPNs to your SAN administrator to configure zoning. The Pure Storage Cinder FC driver will also use WWPNs to automatically register the hypervisor as a host on the FlashArray when the first volume is attached.

### 3.3 Confirm Fabric Zoning

{% include quickstart/fc-zoning-checklist.md %}

### 3.4 Create `/etc/multipath.conf`

```conf
# /etc/multipath.conf — Pure Storage FlashArray FC configuration

defaults {
    user_friendly_names yes
    find_multipaths no
    polling_interval 10
}

blacklist {
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^hd[a-z]"
    devnode "^cciss!c[0-9]d[0-9]*"
}

blacklist_exceptions {
    device {
        vendor "PURE"
        product "FlashArray"
    }
}

devices {
    device {
        vendor                "PURE"
        product               "FlashArray"
        path_selector         "service-time 0"
        path_grouping_policy  "group_by_prio"
        prio                  "alua"
        failback              "immediate"
        path_checker          "tur"
        hardware_handler      "1 alua"
        fast_io_fail_tmo      5
        dev_loss_tmo          60
        no_path_retry         0
    }
}
```

**Key settings:**

| Setting | Value | Reason |
|---------|-------|--------|
| `find_multipaths no` | Required for Pure Storage | Ensures all paths are discovered immediately |
| `blacklist` | All non-storage devices | Prevents multipath from managing system disks |
| `blacklist_exceptions` | `PURE / FlashArray` | Only Pure Storage devices are managed by multipath |
| `prio alua` | ALUA | Uses array-reported path priority for active/optimized selection |
| `fast_io_fail_tmo 5` | 5 seconds | Fail fast on a broken path; PCD re-routes I/O quickly |
| `dev_loss_tmo 60` | 60 seconds | Allow time for transient fabric events to resolve |

### 3.5 Enable and Start Multipath

```bash
sudo systemctl enable multipathd
sudo systemctl restart multipathd
```

### 3.6 Validate Multipath Configuration

```bash
sudo multipath -ll

# Verify no system devices are being managed
sudo multipath -ll | grep -v "PURE\|FlashArray"
```

---

## Step 4: Rescan and Verify FC Connectivity

After zoning and multipath configuration, rescan for any currently-presented volumes:

{% include quickstart/fc-rescan-luns.md %}

At this point the hypervisors are ready. The Pure Storage Cinder FC driver will automatically register each hypervisor as a host on the FlashArray and present volumes when Cinder attach requests are made — no manual host registration is required on the array for Cinder-managed volumes.

---

## Step 5: Verify End-to-End Integration

### 5.1 Create a Test Volume via PCD

1. In the PCD UI, navigate to **Virtual Resources > Volumes**
2. Click **+ Create Volume**
3. Select the `pure-flasharray-fc-backend` backend
4. Create a small test volume (e.g., 10 GB)

### 5.2 Attach to a Test Instance

1. Launch a small test instance on one of the authorized hypervisors
2. Attach the volume to the instance
3. In the PCD UI, verify the volume status shows **In Use**

### 5.3 Verify on the Hypervisor

SSH to the hypervisor where the instance is running:

```bash
# Verify multipath device appeared when volume was attached
sudo multipath -ll | grep PURE

# Verify HBA connections are active
cat /sys/class/fc_host/host*/port_state
```

### 5.4 Verify on the FlashArray

In the FlashArray UI, navigate to **Storage > Hosts** and confirm:
- The hypervisor appears as a registered host with FC connections
- The test volume shows as connected to that host

---

## Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Volume attach fails — no FC device appears | HBA ports not online or zoning incomplete | Verify `cat /sys/class/fc_host/host*/port_state` shows `Online`; confirm zoning with SAN admin |
| Volume attach fails — multipath not configured | `multipathd` not running or `multipath.conf` missing `find_multipaths no` | Verify `systemctl status multipathd` and review `/etc/multipath.conf` |
| FlashArray not registering hypervisor as host | Cinder FC driver not using correct WWPNs | Check `nova-compute` / `cinder-volume` logs; verify HBA driver is loaded and WWPNs are valid |
| Volume attaches but instance cannot access it | Incorrect ALUA configuration | Verify `hardware_handler "1 alua"` and `prio alua` are set in `multipath.conf` |
| `multipath -ll` shows system disks | `blacklist` not configured or `find_multipaths` not set to `no` | Review `multipath.conf`; ensure `blacklist_exceptions` targets only `PURE/FlashArray` |

---

## Important Considerations

1. **Cinder FC driver uses the management IP only.** The driver discovers the FlashArray via `san_ip` and orchestrates volume attachments over FC. No portal or CIDR configuration is required.

2. **The Pure Cinder FC driver auto-registers hosts.** When Cinder attaches a volume to a hypervisor, the driver reads the hypervisor's WWPNs, registers the host on the FlashArray, and presents the volume to that host automatically. Manual host group management is not required for Cinder-managed volumes.

3. **Zoning is still required before the first attach.** The Cinder driver registers the host on the array, but it cannot configure FC switch zoning. Zoning must be in place before any volume attach attempt.

4. **`use_multipath_for_image_xfer true` is mandatory.** Without this, Glance image transfers use a single path device and will fail or produce corrupt images if that path disappears during the transfer.

5. **Confirm `multipathd` is running before authorizing hypervisors in PCD.** Hypervisor role authorization triggers Cinder volume operations; if multipath is not configured at that point, initial volume attachments will fail.

---

## Pre-Flight Checklist

- [ ] FC HBAs installed and cabled to both fabrics on all hypervisor nodes
- [ ] HBA ports report `Online` on all hypervisor nodes (Step 3.2)
- [ ] WWPNs collected from all hypervisor nodes (Step 3.2)
- [ ] Zoning configured on both FC fabrics for all hypervisor WWPNs (Step 3.3)
- [ ] `multipath-tools` installed and `multipathd` enabled on all hypervisors (Step 3.1, 3.5)
- [ ] `/etc/multipath.conf` deployed with `find_multipaths no` and Pure FlashArray device entry (Step 3.4)
- [ ] `multipath -ll` shows no errors on all hypervisors (Step 3.6)
- [ ] PCD Cluster Blueprint configured with `Pure Storage FC` driver (Step 1.4)
- [ ] Hypervisors authorized with **Persistent Storage** role in PCD (Step 2.2)
- [ ] Test volume created and attached successfully (Step 5)
- [ ] FlashArray shows FC host connections from all hypervisors (Step 5.4)
