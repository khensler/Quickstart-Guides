---
layout: default
title: Pure Storage FlashArray Fibre Channel Configuration Guide for HPE VM Essentials
---

# Pure Storage FlashArray Fibre Channel Configuration Guide for HPE VM Essentials

This guide provides step-by-step instructions for configuring Fibre Channel multipath storage from a Pure Storage FlashArray to an HPE VM Essentials (VME) cluster using GFS2 shared datastores.

> **⚠️ Important:** HPE VM Essentials Manager does **not** provide a UI configuration path for Fibre Channel storage. All FC storage configuration is performed via CLI on each cluster host. This guide covers the complete CLI workflow and the VME Manager UI step for creating the GFS2 datastore.

---

## Disclaimer

> **This guide assumes that the Pure Storage FlashArray is already configured and ready for FC connectivity.** This includes:
> - FC ports enabled and cabled to the fabric
> - FC target port IPs assigned across both controllers
> - FC switches configured end-to-end
> - At least one volume created and available for connection
>
> The **only** Pure FlashArray configuration covered in this guide is registering the VME host WWPNs, creating a Host Group, and connecting the volume to that Host Group (Step 3). For initial FlashArray FC port setup, refer to the [Pure Storage FlashArray documentation](https://support.purestorage.com).

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| HPE VME Cluster | Deployed and operational, minimum 3 nodes (required for GFS2) |
| Pure Storage FlashArray | FC volumes provisioned and accessible |
| FC Fabric | Dual-fabric topology, HBAs installed in each cluster node, cabled to both fabrics |
| Access | Root or sudo privileges on all cluster hosts |

{% include quickstart/glossary-link-fc.md %}

---

## Step 1: Install Packages and Enable Multipath

Run on **every cluster host**:

```bash
apt update
apt install -y multipath-tools sg3-utils sysfsutils
systemctl enable --now multipathd
```

---

## Step 2: Verify HBA and Collect WWPNs

Run on **every cluster host**:

{% include quickstart/fc-hba-verify.md %}

> **Collect WWPNs from all cluster hosts** before proceeding. Every host that will access the shared volume must be registered on the array.

---

## Step 3: Register WWPNs and Present Volume

{% include quickstart/fc-zoning-checklist.md %}

**In the Pure FlashArray UI:**

1. Navigate to **Storage → Hosts**
2. Click **+** to create a host entry for each VME node
3. Set **OS Type** to `Linux`
4. Under **Fibre Channel**, paste the WWPN(s) for that host
5. Repeat for all cluster hosts
6. Create a **Host Group** and add all host entries
7. Navigate to **Storage → Volumes**, select your volume, and connect it to the Host Group

---

## Step 4: Rescan for Presented LUNs

Run on **every cluster host**:

{% include quickstart/fc-rescan-luns.md %}

> **All cluster hosts must see the block device before proceeding.** VME Manager will not display the device in the datastore wizard if any host is missing it — no error message is shown.

---

## Step 5: Configure Multipath

Run on **every cluster host**:

{% include quickstart/fc-multipath-conf.md %}

---

## Step 6: Verify Multipath on All Hosts

Run on **every cluster host**:

```bash
multipath -ll
```

**Expected output** — four paths across two ALUA priority groups (active/optimized and active/non-optimized):

```
mpathX (3624a937...) dm-X PURE,FlashArray
size=XXG features='0' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| |- X:0:0:1 sdX  X:X  active ready running
| `- X:0:0:1 sdX  X:X  active ready running
`-+- policy='service-time 0' prio=10 status=enabled
  |- X:0:0:1 sdX  X:X  active ready running
  `- X:0:0:1 sdX  X:X  active ready running
```

---

## Step 7: Create GFS2 Datastore in VME Manager

### 7a. Rescan on All Hosts

Run on **every cluster host**:

```bash
rescan-scsi-bus.sh
```

### 7b. Create the GFS2 Datastore

In the VME Manager UI:

1. Navigate to **Infrastructure → Clusters → [Your Cluster] → Storage → Data Stores**
2. Click **+ ADD**
3. Select **GFS2 Pool** as the type
4. In the **BLOCK DEVICE** dropdown, select the Pure multipath device (`/dev/mapper/<wwid>`)
5. Click **Save**

VME Manager will automatically format the LUN with GFS2, configure DLM, and mount the filesystem on all cluster hosts.

> **Note:** If the block device dropdown shows only local disks, verify that `multipath -ll` shows the Pure device on **every** cluster host, then re-run the rescan command and retry.

---

## Verification

After completing setup, verify on **each cluster host**:

```bash
# Check HBA port state
cat /sys/class/fc_host/host*/port_state

# Check multipath (expect 4 active paths)
multipath -ll

# Verify GFS2 mount
mount | grep gfs2
```

In the VME Manager UI, navigate to **Infrastructure → Clusters → [Your Cluster] → Storage → Data Stores** and confirm the datastore status shows **Online**.

---

## Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Block device not visible in VME datastore wizard | VME Manager does not auto-rescan hypervisor hosts for new block devices | Run `rescan-scsi-bus.sh` on **all** cluster hosts and retry |
| Block device still missing after rescan | One or more hosts are missing the multipath device; GFS2 requires all cluster hosts to see the LUN | Complete Steps 2–6 on the affected host(s); verify with `multipath -ll` on every host |
| Fewer than 4 multipath paths | HBA port not online or zone missing for one HBA port / one fabric | Verify all HBA ports are `Online`; confirm zoning covers both fabrics for this host |
| LUN not visible on any host | Volume not connected to host group, or zoning not complete | Confirm host group connection on FlashArray and verify zoning with SAN admin |
| VME datastore created but I/O errors | `multipath.conf` misconfigured or `find_multipaths` set incorrectly | Verify `find_multipaths no` and `no_path_retry 0` in `/etc/multipath.conf` on all hosts |

---

## Pre-Flight Checklist

- [ ] HBAs installed and cabled to both FC fabrics on all cluster hosts
- [ ] Packages installed and `multipathd` enabled on all cluster hosts (Step 1)
- [ ] WWPNs collected from all cluster hosts (Step 2)
- [ ] HBA ports report `Online` on all cluster hosts (Step 2)
- [ ] Zoning configured on both FC fabrics for all host WWPNs (Step 3)
- [ ] Host entries created on FlashArray for all cluster hosts (Step 3)
- [ ] Host Group created with all hosts added (Step 3)
- [ ] Volume connected to Host Group on FlashArray (Step 3)
- [ ] LUN rescan completed on all cluster hosts (Step 4)
- [ ] `multipath.conf` deployed on all cluster hosts (Step 5)
- [ ] `multipath -ll` shows 4 paths on **every** cluster host (Step 6)
- [ ] Rescan completed before opening VME Manager (Step 7a)
- [ ] GFS2 datastore created and shows **Online** in VME Manager (Step 7b)
- [ ] FlashArray shows FC connections from all cluster hosts
