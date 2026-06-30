---
layout: default
title: OpenShift / Kubernetes — iSCSI Multipathing & NIC Binding via MachineConfig
---

# OpenShift / Kubernetes — iSCSI Multipathing & NIC Binding via MachineConfig

This guide translates the standard Linux iSCSI multipathing and NIC binding configuration into OpenShift **MachineConfig** specs. The underlying configuration is identical to a bare-metal RHEL host — MachineConfig simply delivers those files and systemd units declaratively to Red Hat CoreOS (RHCOS) worker nodes.

> **📘 For the underlying Linux concepts and parameter explanations:** See the [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md) and [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md). This guide focuses on *how* to express those configurations as Kubernetes-native specs.

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

**Option B: Generate at first boot (recommended)**

Use a oneshot systemd unit to generate a unique IQN on first boot if one does not exist:

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

    systemd:
      units:
        - name: iscsid.service
          enabled: true

        # Generate a unique initiator IQN on first boot if none exists
        - name: iscsi-initiator-name.service
          enabled: true
          contents: |
            [Unit]
            Description=Generate iSCSI Initiator Name
            Before=iscsid.service
            ConditionPathExists=!/etc/iscsi/initiatorname.iscsi

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            ExecStart=/bin/bash -c 'echo "InitiatorName=iqn.$(date +%%Y-%%m).$(hostname -d):$(hostname -s)" > /etc/iscsi/initiatorname.iscsi'

            [Install]
            WantedBy=multi-user.target
```

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

MachineConfig prepares the node's iSCSI infrastructure. The **actual iSCSI discovery and session login** is performed by your CSI driver (e.g., Pure Storage CSI, Portworx) when it attaches a volume to a pod.

The MachineConfig ensures:
1. Storage NICs have correct IPs and MTU before the CSI driver runs
2. `iscsid` is running and ready to accept session requests
3. `multipathd` is running and will automatically claim new iSCSI paths
4. Interface bindings are in place so the CSI driver's `iscsiadm --login` commands create sessions on the correct NICs

**No manual `iscsiadm discovery` or `--login` commands are needed** — the CSI driver handles this per-volume.

> **Pure Storage CSI:** Configure the iSCSI interface names in the CSI driver's `StorageClass` or `Secret` as appropriate. The driver uses the iface bindings automatically when `iscsid` is configured for NIC-bound sessions.

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

For environments applying all four configs simultaneously, here is a single combined MachineConfig. This results in a single reboot per node instead of four.

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

    systemd:
      units:
        # Enable iscsid and multipathd at boot
        - name: iscsid.service
          enabled: true

        - name: multipathd.service
          enabled: true

        # Generate unique IQN on first boot if not present
        - name: iscsi-initiator-name.service
          enabled: true
          contents: |
            [Unit]
            Description=Generate iSCSI Initiator Name
            Before=iscsid.service
            ConditionPathExists=!/etc/iscsi/initiatorname.iscsi

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            ExecStart=/bin/bash -c 'echo "InitiatorName=iqn.$(date +%%Y-%%m).$(hostname -d):$(hostname -s)" > /etc/iscsi/initiatorname.iscsi'

            [Install]
            WantedBy=multi-user.target
```

---

## Additional Resources

- [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md)
- [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md) — multipath parameters, APD handling, performance tuning
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [OpenShift MachineConfig documentation](https://docs.openshift.com/container-platform/latest/post_installation_configuration/machine-configuration-tasks.html)
- [OpenShift Machine Config Operator](https://github.com/openshift/machine-config-operator)
