---
layout: default
title: OpenShift / Kubernetes — iSCSI Multipathing & NIC Binding via MachineConfig
---

# OpenShift / Kubernetes — iSCSI Multipathing & NIC Binding via MachineConfig

This guide translates the standard Linux iSCSI multipathing and NIC binding configuration into OpenShift **MachineConfig** specs. The underlying configuration is identical to a bare-metal RHEL host — MachineConfig simply delivers those files and systemd units declaratively to Red Hat CoreOS (RHCOS) worker nodes.

> **For the underlying Linux concepts and parameter explanations:** See the [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md) and [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md). This guide focuses on *how* to express those configurations as Kubernetes-native specs.

---

{% include quickstart/disclaimer.md %}

---

## Table of Contents
- [How MachineConfig Works](#how-machineconfig-works)
- [Prerequisites](#prerequisites)
- [Encoding File Content](#encoding-file-content)
- [MachineConfig 1: Storage NIC Binding](#machineconfig-1-storage-nic-binding)
- [MachineConfig 2: iSCSI Initiator Configuration](#machineconfig-2-iscsi-initiator-configuration)
- [MachineConfig 3: Multipath Configuration](#machineconfig-3-multipath-configuration)
- [MachineConfig 4: iSCSI Interface Bindings](#machineconfig-4-iscsi-interface-bindings)
- [MachineConfig 5: Everpure udev Rules](#machineconfig-5-pure-storage-udev-rules)
- [MachineConfig 6: ARP Settings for Same-Subnet Multipath](#machineconfig-6-arp-settings-for-same-subnet-multipath)
- [Enabling Services](#enabling-services)
- [Applying and Verifying](#applying-and-verifying)
- [CSI Driver Integration](#csi-driver-integration)
- [Troubleshooting](#troubleshooting)
- [Full Combined Reference](#full-combined-reference)

---

## How MachineConfig Works

`MachineConfig` is an OpenShift API object that declaratively manages node-level OS configuration. The **Machine Config Operator (MCO)** watches for changes and rolls them out to node pools one at a time, draining and rebooting each node.

```
MachineConfig ──► MachineConfigPool ──► RHCOS nodes (rolling reboot)
```

**Key properties:**

| Property | Purpose |
|---|---|
| `metadata.labels["machineconfiguration.openshift.io/role"]` | Targets `worker`, `master`, or a custom pool |
| `spec.config.ignition.version` | Must match your OCP version (3.4.0 for OCP 4.9+) |
| `spec.config.files[]` | Files to write to the node filesystem |
| `spec.config.systemd.units[]` | Systemd units to enable/create/override |
| `spec.extensions[]` | Optional OS packages to add (not needed — iscsi/multipath are in RHCOS) |

> **Important:** Every MachineConfig change triggers a **rolling node reboot**. Group related configuration into as few MachineConfig objects as practical to minimize reboot cycles. The MCO merges all MachineConfigs targeting a pool into a single rendered config before applying.

---

## Prerequisites

- OpenShift 4.9+ (Ignition 3.4.0)
- RHCOS worker nodes with dedicated storage NICs
- iSCSI storage array with portal IPs and target IQN
- `oc` CLI with cluster-admin permissions
- Storage NICs must be on a dedicated, non-default network

> **Note:** RHCOS includes `iscsid` and `multipathd` — no package installation is required. MachineConfig only needs to drop configuration files and enable the services.

---

## Encoding File Content

MachineConfig file sources use Ignition data URIs. You must base64-encode file content:

```bash
# Encode a file
cat /etc/multipath.conf | base64 -w0

# Or encode an inline string
echo -n "YOUR_CONTENT" | base64 -w0
```

The `source` field format:
```yaml
source: "data:text/plain;charset=utf-8;base64,<BASE64_ENCODED_CONTENT>"
```

In the specs below, replace `<BASE64: ...>` placeholders with your encoded content. The raw file content is shown as a comment above each encoded field so you know exactly what to encode.

---

## MachineConfig 1: Storage NIC Binding

This creates NetworkManager connection profiles that assign static IPs, set jumbo frames (MTU 9000), and mark the interfaces as non-default-route — the same configuration applied manually via `nmcli` on bare-metal Linux.

**Raw file content for `/etc/NetworkManager/system-connections/storage-1.nmconnection`:**
```ini
[connection]
id=storage-1
type=ethernet
interface-name=<INTERFACE_NAME_1>
autoconnect=true

[ethernet]
mtu=9000

[ipv4]
method=manual
addresses=<HOST_IP_1>/<CIDR>
never-default=true

[ipv6]
method=disabled
```

**Raw file content for `/etc/NetworkManager/system-connections/storage-2.nmconnection`:**
```ini
[connection]
id=storage-2
type=ethernet
interface-name=<INTERFACE_NAME_2>
autoconnect=true

[ethernet]
mtu=9000

[ipv4]
method=manual
addresses=<HOST_IP_2>/<CIDR>
never-default=true

[ipv6]
method=disabled
```

**MachineConfig spec:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-network
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      - path: /etc/NetworkManager/system-connections/storage-1.nmconnection
        mode: 0600         # NM requires 0600 for connection files
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: storage-1.nmconnection content above>"

      - path: /etc/NetworkManager/system-connections/storage-2.nmconnection
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: storage-2.nmconnection content above>"
```

> **Why `never-default=true`?** Prevents the storage interface from becoming the default route. Without this, iSCSI traffic could route incorrectly or displace cluster traffic. This is identical to `ipv4.never-default yes` in the `nmcli` command on bare-metal.

> **Why MTU 9000?** Jumbo frames reduce CPU overhead and improve throughput for large iSCSI transfers. The storage network switches must also be configured for jumbo frames end-to-end.

---

## MachineConfig 2: iSCSI Initiator Configuration

This drops the `iscsid.conf` and `initiatorname.iscsi` files — the same files configured manually on bare-metal Linux — and enables the `iscsid` service.

**Initiator name** — each node must have a **unique IQN**. There are two approaches:

**Option A: Per-node MachineConfig (unique per host)**
Create one MachineConfig per node targeting a node-specific MachineConfigPool, or use a startup script to generate the IQN (see Option B).

**Option B: Generate and validate at first boot (recommended)**

RHCOS images typically ship a default `/etc/iscsi/initiatorname.iscsi` containing a Red Hat default IQN (`iqn.1994-05.com.redhat:<id>`). Nodes cloned from the same image can therefore boot with **identical** IQNs, which breaks multipath and FlashArray host mapping. Use a oneshot systemd unit that runs a small script on every boot to generate a unique IQN when the file is missing or empty, **or when it still contains the shared Red Hat default**:

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-initiator
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      # iscsid.conf — sets automatic node startup
      # Raw content:
      #   node.startup = automatic
      #   node.session.timeo.replacement_timeout = 120
      #   node.conn[0].timeo.login_timeout = 15
      #   node.conn[0].timeo.logout_timeout = 15
      #   node.conn[0].timeo.noop_out_interval = 5
      #   node.conn[0].timeo.noop_out_timeout = 5
      #   node.session.err_timeo.abort_timeout = 15
      #   node.session.err_timeo.lu_reset_timeout = 30
      #   node.session.err_timeo.tgt_reset_timeout = 30
      #   node.session.initial_login_retry_max = 8
      #   node.session.cmds_max = 128
      #   node.session.queue_depth = 32
      #   node.session.iscsi.InitialR2T = No
      #   node.session.iscsi.ImmediateData = Yes
      #   node.session.iscsi.FirstBurstLength = 262144
      #   node.session.iscsi.MaxBurstLength = 16776192
      #   node.session.iscsi.DefaultTime2Wait = 2
      #   node.session.iscsi.DefaultTime2Retain = 0
      #   node.session.iscsi.MaxConnections = 1
      #   node.session.iscsi.FastAbort = Yes
      - path: /etc/iscsi/iscsid.conf
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iscsid.conf content above>"

      # IQN generator/validator script (raw content shown below)
      - path: /usr/local/bin/generate-iscsi-iqn.sh
        mode: 0755
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: generate-iscsi-iqn.sh content below>"

    systemd:
      units:
        - name: iscsid.service
          enabled: true

        # Generate a unique initiator IQN on boot, and replace the shared
        # RHCOS default IQN if the image shipped one.
        - name: iscsi-initiator-name.service
          enabled: true
          contents: |
            [Unit]
            Description=Generate/validate iSCSI Initiator Name
            Before=iscsid.service

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            ExecStart=/usr/local/bin/generate-iscsi-iqn.sh

            [Install]
            WantedBy=multi-user.target
```

**Raw content for `/usr/local/bin/generate-iscsi-iqn.sh`:**
```bash
#!/bin/bash
# Ensure this node has a unique iSCSI initiator IQN.
# RHCOS images often ship a shared default IQN (iqn.1994-05.com.redhat:<id>);
# regenerate when the IQN is missing, empty, or still the Red Hat default.
set -euo pipefail

IQN_FILE=/etc/iscsi/initiatorname.iscsi
current=""
[ -f "$IQN_FILE" ] && current=$(sed -n 's/^InitiatorName=//p' "$IQN_FILE")

if [ -z "$current" ] || [[ "$current" == iqn.1994-05.com.redhat:* ]]; then
    domain=$(hostname -d)
    [ -z "$domain" ] && domain=$(hostname -s)
    new_iqn="iqn.$(date +%Y-%m).${domain}:$(hostname -s)"
    echo "InitiatorName=${new_iqn}" > "$IQN_FILE"
    echo "Generated unique iSCSI IQN: ${new_iqn}"
else
    echo "Existing unique iSCSI IQN retained: ${current}"
fi
```

> **Why not `ConditionPathExists`?** A `ConditionPathExists=!/etc/iscsi/initiatorname.iscsi` guard would skip nodes that already have the file — which is exactly the shared-default case that must be fixed. Running the script every boot is idempotent: once the IQN is unique it is retained (the `else` branch).

> **Register the IQN** — after nodes boot, collect each node's IQN and register it with your storage array before attempting connections:
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host cat /etc/iscsi/initiatorname.iscsi
> ```

---

## MachineConfig 3: Multipath Configuration

Delivers `/etc/multipath.conf` and enables `multipathd`. The configuration is identical to bare-metal Linux — see [RHEL Multipath Configuration](../../rhel/iscsi/BEST-PRACTICES.md#multipath-configuration) for parameter explanations.

**Raw file content for `/etc/multipath.conf`:**
```
defaults {
    find_multipaths      no
    polling_interval     10
    path_selector        "service-time 0"
    path_grouping_policy group_by_prio
    failback             immediate
    no_path_retry        0
}

blacklist {
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^sd[a]$"
    devnode "^nvme"
    devnode "^vd[a-z]"
}

# Add device-specific settings for your storage array.
# Consult your storage vendor documentation for recommended values.
#devices {
#    device {
#        vendor           "VENDOR"
#        product          "PRODUCT"
#        path_selector    "service-time 0"
#        hardware_handler "1 alua"
#        path_grouping_policy group_by_prio
#        prio             alua
#        failback         immediate
#        path_checker     tur
#        fast_io_fail_tmo 10
#        dev_loss_tmo     60
#        no_path_retry    0
#    }
#}
```

**MachineConfig spec:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-multipath
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      - path: /etc/multipath.conf
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: multipath.conf content above>"

    systemd:
      units:
        - name: multipathd.service
          enabled: true
```

> **Why `find_multipaths no`?** Ensures all paths to iSCSI storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. On OpenShift this is especially important because new paths can appear at any time as the CSI driver creates sessions.

> **Why `no_path_retry 0`?** Fails I/O immediately when all paths are down instead of queuing indefinitely. This prevents kernel hung-task warnings and allows pods to receive I/O errors they can recover from. See [APD handling](../../rhel/iscsi/BEST-PRACTICES.md#understanding-apd-all-paths-down-events) for details.

---

## MachineConfig 4: iSCSI Interface Bindings

iSCSI interface bindings ensure each session uses a specific NIC, enabling proper multipath across both storage interfaces. On bare-metal this is done with `iscsiadm -m iface`. In MachineConfig, you write the iface files directly.

**iface file format** — these files live in `/var/lib/iscsi/ifaces/` on RHCOS:

**Raw content for `iface0`:**
```
iface.iscsi_ifacename = iface0
iface.net_ifacename = <INTERFACE_NAME_1>
iface.transport_name = tcp
iface.initiatorname =
iface.ipaddress =
iface.hwaddress =
iface.subnet_mask =
iface.gateway =
iface.bootproto =
iface.vlan_id =
iface.vlan_priority =
iface.vlan_state =
iface.iface_num =
iface.mtu =
iface.port =
```

**Raw content for `iface1`:**
```
iface.iscsi_ifacename = iface1
iface.net_ifacename = <INTERFACE_NAME_2>
iface.transport_name = tcp
iface.initiatorname =
iface.ipaddress =
iface.hwaddress =
iface.subnet_mask =
iface.gateway =
iface.bootproto =
iface.vlan_id =
iface.vlan_priority =
iface.vlan_state =
iface.iface_num =
iface.mtu =
iface.port =
```

**MachineConfig spec:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-ifaces
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      - path: /var/lib/iscsi/ifaces/iface0
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iface0 content above>"

      - path: /var/lib/iscsi/ifaces/iface1
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iface1 content above>"
```

> **Why interface binding?** Without NIC binding, the iSCSI stack may route all sessions through a single interface, reducing path count and defeating multipath redundancy. Binding guarantees `iface0` sessions always exit through `<INTERFACE_NAME_1>` and `iface1` sessions always exit through `<INTERFACE_NAME_2>`, creating true active-active multipath.

---

## MachineConfig 5: Everpure udev Rules

Everpure publishes recommended per-device tuning for FlashArray volumes on Linux. On bare-metal RHEL these settings live in `/etc/udev/rules.d/99-pure-storage.rules`; MachineConfig delivers the identical file to RHCOS. The rules match only devices whose SCSI vendor string is `PURE`, so they never touch local disks or non-Pure LUNs.

The four recommended settings are:

| Setting | Value | Purpose |
|---|---|---|
| `queue/scheduler` | `none` | Flash storage needs no I/O reordering; the multiqueue `none` scheduler minimizes latency and CPU overhead. (On older single-queue kernels this was `noop`.) |
| `queue/add_random` | `0` | Excludes the device from kernel entropy pool contributions, removing per-I/O CPU overhead. |
| `queue/rq_affinity` | `2` | Completes each I/O on the CPU that submitted it, improving cache locality and spreading completion load. |
| `device/timeout` | `60` | Raises the SCSI command timeout to 60s so transient path/controller events don't prematurely fail I/O. |

> **Note:** These rules apply to the underlying `sd*` SCSI paths (the `PURE` vendor match). Multipath (`dm-*`) devices inherit their behavior from the member paths, so matching the `sd*` devices is sufficient.

**Raw file content for `/etc/udev/rules.d/99-pure-storage.rules`:**
```
# Recommended settings for Everpure FlashArray.
# Use none scheduler for high-performance solid-state storage for SCSI devices
ACTION=="add|change", KERNEL=="sd*[!0-9]", SUBSYSTEM=="block", ENV{ID_VENDOR}=="PURE", OPTIONS="nowatch", ATTR{queue/scheduler}="none"
ACTION=="add|change", KERNEL=="dm-[0-9]*", SUBSYSTEM=="block", ENV{DM_NAME}=="3624a937*", OPTIONS="nowatch", ATTR{queue/scheduler}="none"

# Reduce CPU overhead due to entropy collection
ACTION=="add|change", KERNEL=="sd*[!0-9]", SUBSYSTEM=="block", ENV{ID_VENDOR}=="PURE", OPTIONS="nowatch", ATTR{queue/add_random}="0"
ACTION=="add|change", KERNEL=="dm-[0-9]*", SUBSYSTEM=="block", ENV{DM_NAME}=="3624a937*", OPTIONS="nowatch", ATTR{queue/add_random}="0"

# Spread CPU load by redirecting completions to originating CPU
ACTION=="add|change", KERNEL=="sd*[!0-9]", SUBSYSTEM=="block", ENV{ID_VENDOR}=="PURE", OPTIONS="nowatch", ATTR{queue/rq_affinity}="2"
ACTION=="add|change", KERNEL=="dm-[0-9]*", SUBSYSTEM=="block", ENV{DM_NAME}=="3624a937*", OPTIONS="nowatch", ATTR{queue/rq_affinity}="2"

# Set the HBA timeout to 60 seconds
ACTION=="add|change", KERNEL=="sd*[!0-9]", SUBSYSTEM=="block", ENV{ID_VENDOR}=="PURE", OPTIONS="nowatch", ATTR{device/timeout}="60"
```

**MachineConfig spec:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-pure-udev
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      - path: /etc/udev/rules.d/99-pure-storage.rules
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-pure-storage.rules content above>"
```

> **Applying without a reboot** — MachineConfig triggers a rolling reboot which reloads udev automatically. To apply on an already-running node for validation, reload and re-trigger udev:
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host bash -c \
>   "udevadm control --reload-rules && udevadm trigger --subsystem-match=block --action=change"
> ```

> **Verify the settings took effect** (after Pure volumes are attached):
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host bash -c \
>   'for d in $(grep -l PURE /sys/block/sd*/device/vendor | cut -d/ -f4); do \
>      echo -n "$d: "; cat /sys/block/$d/queue/scheduler; done'
> ```
> The active scheduler (in brackets) should be `[none]` for each `PURE` device.

---

## MachineConfig 6: ARP Settings for Same-Subnet Multipath

When both storage NICs share the same subnet — a common iSCSI multipath topology — Linux's default ARP behavior can answer ARP requests for one interface's IP out of the *other* interface (the "ARP flux" problem). This causes the array to see both paths behind a single MAC, collapsing multipath redundancy and producing intermittent path failures. Setting `arp_ignore` and `arp_announce` to `2` forces each interface to reply and announce only for addresses it actually owns.

This delivers `/etc/sysctl.d/99-iscsi-arp.conf`. See [Network Concepts]({{ site.baseurl }}/common/network-concepts.html) for the detailed explanation.

> **Note:** These settings are only required when the storage NICs share a subnet. If each NIC is on its own dedicated subnet, they are unnecessary (but harmless). Replace the interface-specific `ens1f0`/`ens1f1` entries with your actual storage interface names.

**Raw file content for `/etc/sysctl.d/99-iscsi-arp.conf`:**
```
# ARP settings for same-subnet multipath (CRITICAL)
# Prevents ARP responses on wrong interface when multiple NICs share same subnet
# See: Network Concepts documentation for detailed explanation
net.ipv4.conf.all.arp_ignore = 2
net.ipv4.conf.default.arp_ignore = 2
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_announce = 2
# Interface-specific (adjust interface names as needed)
net.ipv4.conf.ens1f0.arp_ignore = 2
net.ipv4.conf.ens1f1.arp_ignore = 2
net.ipv4.conf.ens1f0.arp_announce = 2
net.ipv4.conf.ens1f1.arp_announce = 2
```

**MachineConfig spec:**

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-arp
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      - path: /etc/sysctl.d/99-iscsi-arp.conf
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-iscsi-arp.conf content above>"
```

> **Applying without a reboot** — MachineConfig triggers a rolling reboot which reloads sysctl automatically. To apply on an already-running node for validation:
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host sysctl --system
> ```

> **Verify the settings took effect:**
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host bash -c \
>   'sysctl net.ipv4.conf.all.arp_ignore net.ipv4.conf.all.arp_announce'
> ```
> Both should report `= 2`.

---

## Enabling Services

The systemd `enabled: true` fields above configure the units to start on boot. For the initial enable without a reboot, you can run:

```bash
# Run on a specific node via oc debug
oc debug node/<NODE_NAME> -- chroot /host systemctl enable --now iscsid multipathd
```

MachineConfig-managed nodes will have these enabled automatically after the MCO applies and reboots.

---

## Applying and Verifying

### Apply MachineConfigs

```bash
# Apply all at once (MCO merges and reboots once per node)
oc apply -f 99-worker-iscsi-network.yaml
oc apply -f 99-worker-iscsi-initiator.yaml
oc apply -f 99-worker-iscsi-multipath.yaml
oc apply -f 99-worker-iscsi-ifaces.yaml
oc apply -f 99-worker-pure-udev.yaml
oc apply -f 99-worker-iscsi-arp.yaml
```

### Watch the Rollout

```bash
# Watch MachineConfigPool update progress
oc get mcp worker -w

# Detailed node-by-node status
oc get nodes -o wide -w

# View MCO operator logs
oc logs -n openshift-machine-config-operator \
    -l k8s-app=machine-config-operator -f
```

A healthy pool transitions through:
```
UPDATED   UPDATING   DEGRADED
0/N       1/N        0         ← rolling update in progress
N/N       0/N        0         ← complete
```

### Verify Configuration on a Node

```bash
# Open a debug shell on a worker node
oc debug node/<NODE_NAME>
chroot /host

# Verify NIC configuration
nmcli connection show storage-1
nmcli device show <INTERFACE_NAME_1>

# Verify iSCSI initiator name
cat /etc/iscsi/initiatorname.iscsi

# Verify iscsid config
cat /etc/iscsi/iscsid.conf | grep node.startup

# Verify multipath config
cat /etc/multipath.conf

# Verify services are running
systemctl status iscsid multipathd

# Verify iface bindings
iscsiadm -m iface

# Check active multipath devices (populated after CSI creates sessions)
multipath -ll
```

### Verify Rendered MachineConfig

```bash
# See the merged config the MCO generates for the worker pool
oc get mc rendered-worker-<HASH> -o yaml

# See which MachineConfigs are included
oc get mcp worker -o jsonpath='{.spec.configuration.source}' | jq .
```

---

## CSI Driver Integration

MachineConfig prepares the node's iSCSI infrastructure. The **actual iSCSI discovery and session login** is performed by your CSI driver (e.g., Portworx to configure both FlashArray and FlashBlade CSI or Portworx Enterprise) when it attaches a volume to a pod.

The MachineConfig ensures:
1. Storage NICs have correct IPs and MTU before the CSI driver runs
2. `iscsid` is running and ready to accept session requests
3. `multipathd` is running and will automatically claim new iSCSI paths
4. Interface bindings are in place so the CSI driver's `iscsiadm --login` commands create sessions on the correct NICs

**No manual `iscsiadm discovery` or `--login` commands are needed** — the CSI driver handles this per-volume.

> **Portworx Operator Configurations:** Configure the iSCSI interface names in the Portworx Operator's  `StorageCluster`. The CRD uses the iface bindings automatically when `iscsid` is configured for NIC-bound sessions.

---

## Troubleshooting

### MachineConfig Not Applied

```bash
# Check if node is in a degraded state
oc get mcp worker
oc get node -o custom-columns=NAME:.metadata.name,STATE:.metadata.annotations."machineconfiguration\.openshift\.io/state"

# Get degradation reason
oc describe machineconfigpool worker | grep -A 10 Degraded
```

### Service Not Starting After Reboot

```bash
oc debug node/<NODE_NAME> -- chroot /host journalctl -u iscsid -u multipathd --no-pager -n 50
```

### Wrong NIC or No Paths

```bash
oc debug node/<NODE_NAME> -- chroot /host bash -c "iscsiadm -m session -P 3"
```

Look for `Iface Name` in the output — it should show `iface0` and `iface1`, not `default`.

### Multipath Not Picking Up iSCSI Devices

```bash
oc debug node/<NODE_NAME> -- chroot /host bash -c "multipath -ll && multipath -v3 2>&1 | head -50"
```

If devices are being blacklisted, adjust the `blacklist` section in `multipath.conf`. Verify `find_multipaths no` is set.

### NIC Configuration Conflict

If a node's NIC already has a NetworkManager connection (from DHCP or installer), the MachineConfig-deployed `.nmconnection` file may conflict. Check:

```bash
oc debug node/<NODE_NAME> -- chroot /host nmcli connection show
```

If duplicate connections exist, remove the old one via a MachineConfig oneshot unit or adjust the `id` in your connection file.

---

## Full Combined Reference

For environments applying all configs simultaneously, here is a single combined MachineConfig. This results in a single reboot per node instead of one per object.

[Back to Table of Contents](#table-of-contents)

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-iscsi-full
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    files:
      # Storage NIC 1 — NetworkManager connection
      - path: /etc/NetworkManager/system-connections/storage-1.nmconnection
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: storage-1.nmconnection>"

      # Storage NIC 2 — NetworkManager connection
      - path: /etc/NetworkManager/system-connections/storage-2.nmconnection
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: storage-2.nmconnection>"

      # iscsid configuration
      - path: /etc/iscsi/iscsid.conf
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iscsid.conf>"

      # IQN generator/validator script
      - path: /usr/local/bin/generate-iscsi-iqn.sh
        mode: 0755
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: generate-iscsi-iqn.sh>"

      # dm-multipath configuration
      - path: /etc/multipath.conf
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: multipath.conf>"

      # iSCSI interface binding — NIC 1
      - path: /var/lib/iscsi/ifaces/iface0
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iface0>"

      # iSCSI interface binding — NIC 2
      - path: /var/lib/iscsi/ifaces/iface1
        mode: 0600
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: iface1>"

      # Everpure recommended udev rules
      - path: /etc/udev/rules.d/99-pure-storage.rules
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-pure-storage.rules>"

      # ARP settings for same-subnet multipath
      - path: /etc/sysctl.d/99-iscsi-arp.conf
        mode: 0644
        overwrite: true
        contents:
          source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-iscsi-arp.conf>"

    systemd:
      units:
        # Enable iscsid and multipathd at boot
        - name: iscsid.service
          enabled: true

        - name: multipathd.service
          enabled: true

        # Generate a unique IQN on boot; replace the shared RHCOS default if present
        - name: iscsi-initiator-name.service
          enabled: true
          contents: |
            [Unit]
            Description=Generate/validate iSCSI Initiator Name
            Before=iscsid.service

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            ExecStart=/usr/local/bin/generate-iscsi-iqn.sh

            [Install]
            WantedBy=multi-user.target
```

---

## Additional Resources

- [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md)
- [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md) — multipath parameters, APD handling, performance tuning
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Network Concepts]({{ site.baseurl }}/common/network-concepts.html) — ARP flux and same-subnet multipath
- [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array) — Portworx's own host-prep guidance (multipath, udev, iSCSI/NVMe connectivity)
- [OpenShift MachineConfig documentation](https://docs.openshift.com/container-platform/latest/post_installation_configuration/machine-configuration-tasks.html)
- [OpenShift Machine Config Operator](https://github.com/openshift/machine-config-operator)