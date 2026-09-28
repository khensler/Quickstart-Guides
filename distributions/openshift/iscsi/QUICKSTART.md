---
layout: default
title: OpenShift — iSCSI on Everpure FlashArray with Portworx
---

# OpenShift — iSCSI on Everpure FlashArray with Portworx

This guide is an end-to-end quick start for connecting an OpenShift 4.x cluster to Everpure FlashArray over iSCSI. It covers pre-flight validation, storage-network configuration, the worker-node iSCSI and multipath configuration delivered as **MachineConfig**, a node disruption policy so those MachineConfigs apply without rebooting the workers, Portworx operator and StorageCluster deployment, and final validation with a StorageClass, PVC, test pod, and optionally a virtual machine.

The node-level configuration is identical to a bare-metal RHEL host — MachineConfig simply delivers those files and systemd units declaratively to Red Hat CoreOS (RHCOS) worker nodes, which are immutable and cannot be configured by hand.

> **For the underlying Linux concepts and parameter explanations:** See the [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md) and [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md). This guide focuses on *how* to express those configurations as Kubernetes-native specs.

---

{% include quickstart/disclaimer.md %}

{% include quickstart/glossary-link-iscsi.md %}

---

## Overview

The procedure has four distinct phases. Read this section before starting so you know which decisions are made where.

| Phase | Steps | What it does |
|---|---|---|
| Validate | 1 | Confirm cluster health, connectivity, and collect each node's iSCSI IQN |
| Network | 2 | Give each worker node its storage IPs and MTU |
| Node config | 3–10 | Deliver `iscsid.conf`, `multipath.conf`, iface bindings, udev rules, and ARP sysctls via MachineConfig, under a node disruption policy so the rollout restarts services instead of rebooting nodes |
| Storage stack | 11–15 | Install Portworx, connect it to FlashArray, and provision a volume |

**Who logs in to the array.** Steps 3–10 prepare the node. The actual iSCSI discovery and session login is performed by **Portworx** when it attaches a volume — you do not run `iscsiadm --login` as part of normal operation. The manual discovery commands in Step 1 exist only to prove connectivity before Portworx is installed.

**By default, every MachineConfig change triggers a rolling node reboot.** Nothing in this guide actually needs one — every change is a configuration file or a service that can be reloaded in place — so Step 9 creates a **node disruption policy** that tells the Machine Config Operator (MCO) to reload or restart the affected service instead of rebooting. Still group related configuration into as few MachineConfig objects as practical: the MCO merges all MachineConfigs targeting a pool into a single rendered config before applying, so applying Steps 4–8 together costs one rollout (one drain) per node rather than five. A combined single-object example is in [Additional Notes](#additional-notes). On clusters older than OpenShift 4.17 the policy is not available and each rollout reboots the pool as before.

---

## Prerequisites

- OpenShift 4.9+ (Ignition spec 3.4.0; 3.2.0 also accepted on older releases)
- OpenShift 4.17+ to apply the node configuration without a reboot (node disruption policies are GA in 4.17). The MachineConfigs work on older releases too, but every rollout reboots the pool.
- Worker nodes healthy and schedulable, with dedicated storage NICs
- Everpure FlashArray configured and reachable on both the management and data paths
- IP reachability between worker nodes and the FlashArray iSCSI ports (TCP 3260)
- `oc` CLI with cluster-admin permissions
- Storage NICs on a dedicated, non-default network
- **Kubernetes NMState Operator** installed with an `NMState` instance created, if you plan to configure networking declaratively in Step 2 (Option A). Find it under **Ecosystem → Software Catalog** in the OpenShift web console.

> **Note:** RHCOS includes `iscsid` and `multipathd` — no package installation is required, and `spec.extensions[]` is not needed. MachineConfig only has to drop configuration files and enable the services.

---

## Background

`MachineConfig` is an OpenShift API object that declaratively manages node-level OS configuration. The MCO watches for changes and rolls them out to node pools one at a time. By default that means draining and rebooting each node; a **node disruption policy** replaces the reboot with a service reload or restart for the files and units it names.

```
MachineConfig ──► MachineConfigPool ──► RHCOS nodes (rolling update: reboot by default,
                                         or reload/restart a service under a node disruption policy)
```

**Key properties:**

| Property | Purpose |
|---|---|
| `metadata.labels["machineconfiguration.openshift.io/role"]` | Targets `worker`, `master`, or a custom pool |
| `spec.config.ignition.version` | Must match your OCP version (3.4.0 for OCP 4.9+) |
| `spec.config.storage.files[]` | Files to write to the node filesystem |
| `spec.config.systemd.units[]` | Systemd units to enable/create/override |

> **Why not just SSH in and edit the files?** RHCOS is an immutable operating system. Manual edits to `/etc/multipath.conf`, `/etc/iscsi/iscsid.conf` or anything else under `/etc` are wiped on the next node reprovision, and `mpathconf --enable` will not survive either. MachineConfig is the only durable mechanism.

### Node Disruption Policies

Since OpenShift 4.17 the MCO consults a cluster-wide `MachineConfiguration` object (`operator.openshift.io/v1`, always named `cluster`) before deciding how to apply a rendered config. Its `spec.nodeDisruptionPolicy` maps file paths and systemd unit names to the actions the MCO takes when those items change:

| Action | What the MCO does |
|---|---|
| `None` | Writes the change and nothing else |
| `Reload` / `Restart` | `systemctl reload` / `systemctl restart` the named service |
| `DaemonReload` | `systemctl daemon-reload`, needed before systemd can start a unit whose file was just written |
| `Drain` | Cordons and drains the node first, but does not reboot it |
| `Reboot` | The default for anything the policy does not mention |

Three rules matter for this guide:

- **Anything not covered reboots.** The MCO diffs the old and new rendered configs; if even one changed file or unit has no policy entry, the whole update falls back to a reboot. Adding a new file counts as a change.
- **Paths match exactly or by directory.** A policy for `/var/lib/iscsi/ifaces` covers every file under it, which is how this guide handles per-NIC iface files without naming them.
- **Actions run in the order written, and the MCO does not check that they are sufficient.** Restarting the wrong service still counts as a successful rebootless update, so the verification in Step 10 is not optional.

---

## Step 1: Run Pre-Flight Validation

These commands confirm prerequisites — they do not configure anything. Run them before applying any MachineConfig or deploying Portworx.

### Cluster and Node Health

```bash
# All operators should show Available=True, Degraded=False
oc get co

# All participating worker nodes should show Ready
oc get nodes -o wide
```

### Management Connectivity to FlashArray

From a worker node debug shell:

```bash
oc debug node/<WORKER_NODE_NAME>
chroot /host

# Basic reachability (if ICMP is permitted)
ping <FLASHARRAY_MGMT_IP>

# TCP reachability on management port 443.
# socat connects and hangs on success; an error indicates unreachable.
socat - TCP:<FLASHARRAY_MGMT_IP>:443
```

### iSCSI Pre-Flight

```bash
oc debug node/<WORKER_NODE_NAME> -- chroot /host bash -c '
  cat /etc/iscsi/initiatorname.iscsi
  systemctl is-active iscsid multipathd
  nc -zv <FLASHARRAY_ISCSI_IP> 3260'
```

### Collect the IQN From Every Worker

This is the single most important pre-flight check for iSCSI. Every host has an iSCSI Initiator Name (IQN) that the FlashArray uses to identify it. When OpenShift nodes are deployed from a common image — an Assisted Installer ISO, a golden template — **they frequently all boot with the identical IQN**. The array then sees every node as one host, which breaks host mapping and multipath in ways that are painful to diagnose later.

Run this loop from your management station:

```bash
for node in $(oc get nodes -l node-role.kubernetes.io/worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== $node ==="
  oc debug node/$node -- chroot /host bash -c \
    "cat /etc/iscsi/initiatorname.iscsi && cat /etc/machine-id"
done
```

> **⚠️ If two or more nodes report the same IQN — and they almost certainly will — write that value down.** That is your **template IQN**, and you need it in Step 4. A default RHCOS image typically ships `iqn.1994-05.com.redhat:<id>`; seeing that string on more than one node confirms the problem rather than confirming health.

Also note whether each worker can reach TCP 3260 from **both** storage IPs. If it cannot, fix networking in Step 2 before going any further.

---

## Step 2: Configure Storage Networking

Each worker node needs two storage interfaces with static IPs and jumbo frames. There are two supported ways to deliver that. Pick one — do not apply both.

| | Option A: NMState (NNCP) | Option B: MachineConfig (NetworkManager) |
|---|---|---|
| Mechanism | `NodeNetworkConfigurationPolicy` | `.nmconnection` files in a MachineConfig |
| Reboot required | No | Yes (rolling; not covered by the Step 9 node disruption policy) |
| Per-node specs | One NNCP per node (unique IPs) | One MachineConfig per pool, or per node |
| Requires | NMState Operator | Nothing extra |

Option A is recommended on clusters that already run the NMState Operator, mainly because it applies without a reboot and keeps per-node addressing declarative.

### Option A: NMState NodeNetworkConfigurationPolicy

Each worker node ends up with two standalone VLAN subinterfaces, each with its own IP on the storage subnet, at MTU 9000. **No OS-level bond is needed** — Portworx manages both paths itself (see Step 13).

Plan the addresses first; you need two per worker:

| Worker node | NIC 1 VLAN IP | NIC 2 VLAN IP |
|---|---|---|
| `<WORKER_1_HOSTNAME>` | `<WORKER_1_NIC1_IP>/<PREFIX>` | `<WORKER_1_NIC2_IP>/<PREFIX>` |
| `<WORKER_2_HOSTNAME>` | `<WORKER_2_NIC1_IP>/<PREFIX>` | `<WORKER_2_NIC2_IP>/<PREFIX>` |
| `<WORKER_3_HOSTNAME>` | `<WORKER_3_NIC1_IP>/<PREFIX>` | `<WORKER_3_NIC2_IP>/<PREFIX>` |

> **⚠️ Two IPs on one subnet — do not reach for policy-based routing.** When two interfaces hold addresses from the same subnet, Linux's single default route means egress is not automatically pinned to the interface an address belongs to. It is tempting to solve this with policy-based routing (per-NIC route tables plus source-based `ip rule` entries). **Don't.** It adds a second, parallel source of truth for path selection that has to be kept in sync with the iSCSI configuration by hand, and it diverges from the Everpure Linux baseline.
>
> The supported answer is **iSCSI interface binding** (Step 6) together with the ARP sysctls (Step 8). Binding tells `iscsid` which NIC each session belongs to, so every session's egress is deterministic at the iSCSI layer, where multipath can actually see and act on it. ARP `arp_ignore`/`arp_announce = 2` stops the two NICs answering for each other's addresses. Together these give correct per-path behaviour with no custom routing.
>
> Leave the default route table alone. Give each storage interface its IP, its MTU, and nothing else. If you would rather avoid same-subnet addressing entirely, put each storage NIC on its own VLAN/subnet or bond the interfaces — both are valid, and both also still want the iface bindings in Step 6.

Create **one NNCP per worker node**, since each node's IPs differ:

```yaml
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: storage-iscsi-worker-1    # unique per node
spec:
  nodeSelector:
    kubernetes.io/hostname: <WORKER_1_HOSTNAME>
  desiredState:
    interfaces:
      - name: <NIC1>.<VLAN_ID>    # e.g. ens1f0np0.210
        type: vlan
        state: up
        mtu: 9000
        vlan:
          base-iface: <NIC1>
          id: <VLAN_ID>
        ipv4:
          enabled: true
          address:
            - ip: <WORKER_1_NIC1_IP>
              prefix-length: <PREFIX>
          dhcp: false

      - name: <NIC2>.<VLAN_ID>    # e.g. ens1f1np1.210
        type: vlan
        state: up
        mtu: 9000
        vlan:
          base-iface: <NIC2>
          id: <VLAN_ID>
        ipv4:
          enabled: true
          address:
            - ip: <WORKER_1_NIC2_IP>
              prefix-length: <PREFIX>
          dhcp: false
```

Note what is deliberately absent: no `routes` stanza, no `route-rules`, no default gateway on either storage interface. The storage network is reached by the connected route each address creates, and session-to-NIC affinity is handled by the iface bindings in Step 6.

Apply from the CLI, or from the web console via **Networking → NodeNetworkConfigurationPolicy → Create → With YAML**. Repeat for each worker node, updating the hostname, both IPs, and both route-rule source IPs each time.

### Option B: NetworkManager Connection Files via MachineConfig

This writes NetworkManager connection profiles directly. Use it when the NMState Operator is not available.

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
    storage:
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

> **Why `never-default=true`?** Prevents the storage interface from becoming the default route. Without it, iSCSI traffic could route incorrectly or displace cluster traffic. This is identical to `ipv4.never-default yes` in the `nmcli` command on bare-metal.

> **Why MTU 9000?** Jumbo frames reduce CPU overhead and improve throughput for large iSCSI transfers. The storage network switches must also be configured for jumbo frames end-to-end, or the path will silently fragment or black-hole.

### Verify Networking Before Continuing

```bash
# NMState only - both policies and per-node enactments must be Available/Succeeded
oc get nncp
oc get nnce

# Confirm both storage interfaces are up with the right IPs and MTU
oc debug node/<WORKER_NODE_NAME> -- chroot /host ip -br addr show

# Confirm iSCSI reachability from each storage IP
oc debug node/<WORKER_NODE_NAME> -- chroot /host bash -c \
  "ping -c2 -I <WORKER_1_NIC1_IP> <FA_ISCSI_IP_1> && \
   ping -c2 -I <WORKER_1_NIC2_IP> <FA_ISCSI_IP_2>"
```

Both interfaces should show `UP`, their configured address, and MTU 9000. Binding each `ping` to a source address with `-I` is what makes the second check meaningful — an unbound `ping` proves only that *some* interface can reach the array.

---

## Step 3: Encode File Content for MachineConfig

MachineConfig file sources use Ignition data URIs, so every file in Steps 4–8 must be base64-encoded:

```bash
# Encode a file
base64 -w0 /path/to/multipath.conf

# Or encode an inline string
echo -n "YOUR_CONTENT" | base64 -w0
```

The `source` field format:
```yaml
source: "data:text/plain;charset=utf-8;base64,<BASE64_ENCODED_CONTENT>"
```

In the specs below, replace each `<BASE64: ...>` placeholder with your encoded content. The raw file content is shown above each encoded field so you know exactly what to encode.

---

## Step 4: Configure the iSCSI Initiator and Guarantee Unique IQNs

This delivers `/etc/iscsi/iscsid.conf`, enables `iscsid`, and installs a oneshot unit that replaces a duplicated IQN with a unique one.

**Raw file content for `/etc/iscsi/iscsid.conf`:**
```
node.startup = automatic
node.session.timeo.replacement_timeout = 120
node.conn[0].timeo.login_timeout = 15
node.conn[0].timeo.logout_timeout = 15
node.conn[0].timeo.noop_out_interval = 5
node.conn[0].timeo.noop_out_timeout = 5
node.session.err_timeo.abort_timeout = 15
node.session.err_timeo.lu_reset_timeout = 30
node.session.err_timeo.tgt_reset_timeout = 30
node.session.initial_login_retry_max = 8
node.session.cmds_max = 128
node.session.queue_depth = 32
node.session.iscsi.InitialR2T = No
node.session.iscsi.ImmediateData = Yes
node.session.iscsi.FirstBurstLength = 262144
node.session.iscsi.MaxBurstLength = 16776192
node.session.iscsi.DefaultTime2Wait = 2
node.session.iscsi.DefaultTime2Retain = 0
node.session.iscsi.MaxConnections = 1
node.session.iscsi.FastAbort = Yes
```

> **⚠️ Deviation to be aware of: `node.startup`.** The value above (`automatic`) is the Everpure standard for Linux iSCSI hosts and is what this guide uses. Some Portworx-specific material recommends `node.startup = manual` instead, on the grounds that Portworx owns session login and `automatic` can produce "session already exists" errors at boot. If you hit that symptom on a Portworx-managed cluster, switching this one value to `manual` is the documented remedy — change it here and re-apply, rather than editing the file on a node.

**Raw content for `/usr/local/bin/generate-iscsi-iqn.sh`:**
```bash
#!/bin/bash
# Ensure this node has a unique iSCSI initiator IQN.
# Cloned RHCOS images frequently ship an identical IQN across every node
# (commonly iqn.1994-05.com.redhat:<id>). Regenerate when the IQN is
# missing, empty, matches the Red Hat default, or matches the template IQN
# collected in Step 1.
set -euo pipefail

IQN_FILE=/etc/iscsi/initiatorname.iscsi
TEMPLATE_IQN="<TEMPLATE_IQN_FROM_STEP_1>"

current=""
[ -f "$IQN_FILE" ] && current=$(sed -n 's/^InitiatorName=//p' "$IQN_FILE")

if [ -z "$current" ] \
   || [ "$current" = "$TEMPLATE_IQN" ] \
   || [[ "$current" == iqn.1994-05.com.redhat:* ]]; then
    domain=$(hostname -d)
    [ -z "$domain" ] && domain=$(hostname -s)
    new_iqn="iqn.$(date +%Y-%m).${domain}:$(cat /proc/sys/kernel/random/uuid)"
    echo "InitiatorName=${new_iqn}" > "$IQN_FILE"
    echo "Generated unique iSCSI IQN: ${new_iqn}"
else
    echo "Existing unique iSCSI IQN retained: ${current}"
fi
```

**MachineConfig spec:**

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
    storage:
      files:
        - path: /etc/iscsi/iscsid.conf
          mode: 0600
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: iscsid.conf content above>"

        - path: /usr/local/bin/generate-iscsi-iqn.sh
          mode: 0755
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: generate-iscsi-iqn.sh content above>"

    systemd:
      units:
        - name: iscsid.service
          enabled: true

        # Generate a unique initiator IQN on boot, and replace the shared
        # template IQN if the image shipped one.
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

> **How this applies without a reboot.** `iscsid` reads the initiator name only at start-up. The node disruption policy in Step 9 therefore runs `iscsi-initiator-name.service` and then restarts `iscsid.service`, in that order, for every change that can touch the IQN.

> **Why not `ConditionPathExists`?** A `ConditionPathExists=!/etc/iscsi/initiatorname.iscsi` guard would skip nodes that already have the file — which is exactly the shared-default case that must be fixed. Running the script every boot is idempotent: once the IQN is unique it is retained (the `else` branch).

> **Register the IQNs** — after the rollout in Step 10, collect each node's IQN and register it with the FlashArray before attempting connections. `New-Pfa2Host` and the FlashArray GUI both take the IQN list per host; pass every IQN a node reports.
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host cat /etc/iscsi/initiatorname.iscsi
> ```

---

## Step 5: Configure Multipath

Delivers `/etc/multipath.conf` and enables `multipathd`. The configuration is identical to bare-metal Linux — see [RHEL Multipath Configuration](../../rhel/iscsi/BEST-PRACTICES.md#multipath-configuration) for parameter explanations.

**Raw file content for `/etc/multipath.conf`:**
```
defaults {
    find_multipaths      no
    user_friendly_names  no
    enable_foreign       "^$"
    polling_interval     10
    path_selector        "service-time 0"
    path_grouping_policy group_by_prio
    failback             immediate
    no_path_retry        0
}

devices {
    device {
        vendor               "PURE"
        product              "FlashArray"
        path_selector        "service-time 0"
        hardware_handler     "1 alua"
        path_grouping_policy group_by_prio
        prio                 alua
        failback             immediate
        path_checker         tur
        fast_io_fail_tmo     10
        user_friendly_names  no
        no_path_retry        0
        features             0
        dev_loss_tmo         60
    }
}

blacklist_exceptions {
    property "(SCSI_IDENT_|ID_WWN)"
}

blacklist {
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^sd[a]$"
    devnode "^nvme"
    devnode "^vd[a-z]"
    devnode "^pxd[0-9]*"
    devnode "^pxd*"
    device {
        vendor  "VMware"
        product "Virtual disk"
    }
}
```

> **`PURE` and `FlashArray` are literal SCSI identifier strings**, not product branding. Do not rewrite them.

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
    storage:
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

> **Why `find_multipaths no`?** Ensures all paths to iSCSI storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. On OpenShift this matters especially because new paths appear at any time as the CSI driver creates sessions. Some Portworx material shows `find_multipaths yes`; this guide uses `no` for consistency with the Everpure Linux baseline. Use one value or the other, not a mixture across nodes.

> **Why `no_path_retry 0`?** Fails I/O immediately when all paths are down instead of queuing indefinitely. This prevents kernel hung-task warnings and lets pods receive I/O errors they can recover from. See [How long an outage the host survives](../../rhel/iscsi/BEST-PRACTICES.md#how-long-an-outage-the-host-survives).

> **Why blacklist `pxd`?** Portworx presents its own `pxd*` block devices. Leaving them unblacklisted lets multipath attempt to claim them, which produces spurious paths and confusing `multipath -ll` output.

> **Never run `mpathconf --enable` on RHCOS.** It writes to `/etc`, which is reverted on reprovision. `multipathd.service` is enabled by the `systemd` stanza above.

---

## Step 6: Configure iSCSI Interface Bindings

iSCSI interface bindings ensure each session uses a specific NIC, enabling proper multipath across both storage interfaces. On bare-metal this is done with `iscsiadm -m iface`. In MachineConfig, you write the iface files directly.

The iface files live in `/var/lib/iscsi/ifaces/`. Name each file after the interface it binds — if you used VLAN subinterfaces in Step 2 Option A, the filename and both `iface.*_ifacename` values are the subinterface name.

**Raw content for `/var/lib/iscsi/ifaces/<NIC1>.<VLAN_ID>`:**
```
# BEGIN RECORD 6.2.1.9
iface.iscsi_ifacename = <NIC1>.<VLAN_ID>
iface.net_ifacename = <NIC1>.<VLAN_ID>
iface.prefix_len = 0
iface.transport_name = tcp
iface.vlan_id = 0
iface.vlan_priority = 0
iface.iface_num = 0
iface.mtu = 0
iface.port = 0
iface.tos = 0
iface.ttl = 0
iface.tcp_wsf = 0
iface.tcp_timer_scale = 0
iface.def_task_mgmt_timeout = 0
iface.erl = 0
iface.max_receive_data_len = 0
iface.first_burst_len = 0
iface.max_outstanding_r2t = 0
iface.max_burst_len = 0
# END RECORD
```

Repeat the file for `<NIC2>.<VLAN_ID>`, changing both `iface.iscsi_ifacename` and `iface.net_ifacename`. Create one file per storage NIC. The node disruption policy in Step 9 covers the whole `/var/lib/iscsi/ifaces` directory, so the file names do not need to appear in it.

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
    storage:
      files:
        - path: /var/lib/iscsi/ifaces/<NIC1>.<VLAN_ID>
          mode: 0600
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: NIC1 iface content above>"

        - path: /var/lib/iscsi/ifaces/<NIC2>.<VLAN_ID>
          mode: 0600
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: NIC2 iface content above>"
```

> **Why interface binding?** Without NIC binding, the iSCSI stack may route all sessions through a single interface, reducing path count and defeating multipath redundancy. Binding guarantees each session exits through the interface it is named for, creating true active-active multipath. The corresponding Portworx-side setting is `PURE_ISCSI_ALLOWED_IFACES` in Step 13 — the two must name the same interfaces.

---

## Step 7: Apply the Everpure udev Rules

Everpure publishes recommended per-device tuning for FlashArray volumes on Linux. On bare-metal RHEL these settings live in `/etc/udev/rules.d/99-pure-storage.rules`; MachineConfig delivers the identical file to RHCOS. The rules match only devices whose SCSI vendor string is `PURE`, so they never touch local disks or non-Everpure LUNs.

The four recommended settings are:

| Setting | Value | Purpose |
|---|---|---|
| `queue/scheduler` | `none` | Flash storage needs no I/O reordering; the multiqueue `none` scheduler minimizes latency and CPU overhead. (On older single-queue kernels this was `noop`.) |
| `queue/add_random` | `0` | Excludes the device from kernel entropy pool contributions, removing per-I/O CPU overhead. |
| `queue/rq_affinity` | `2` | Completes each I/O on the CPU that submitted it, improving cache locality and spreading completion load. |
| `device/timeout` | `60` | Raises the SCSI command timeout to 60s so transient path/controller events don't prematurely fail I/O. |

> **Note:** These rules apply to the underlying `sd*` SCSI paths (the `PURE` vendor match). Multipath (`dm-*`) devices inherit their behavior from the member paths, so matching the `sd*` devices is sufficient; the `dm-*` lines below are belt-and-braces.

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
    storage:
      files:
        - path: /etc/udev/rules.d/99-pure-storage.rules
          mode: 0644
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-pure-storage.rules content above>"
```

> **How the rules take effect** — the node disruption policy in Step 9 reloads `systemd-udevd` when this file changes, so every FlashArray device discovered from then on gets the settings. A reload does not re-evaluate devices that already exist; if you change the rules on a node that already has FlashArray volumes attached, trigger them by hand:
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host \
>   udevadm trigger --subsystem-match=block --action=change
> ```

> **Verify the settings took effect** (after Everpure volumes are attached):
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host bash -c \
>   'for d in $(grep -l PURE /sys/block/sd*/device/vendor | cut -d/ -f4); do \
>      echo -n "$d: "; cat /sys/block/$d/queue/scheduler; done'
> ```
> The active scheduler (in brackets) should be `[none]` for each `PURE` device.

---

## Step 8: Configure ARP for Same-Subnet Multipath

When both storage NICs share the same subnet — a common iSCSI multipath topology — Linux's default ARP behavior can answer ARP requests for one interface's IP out of the *other* interface (the "ARP flux" problem). The array then sees both paths behind a single MAC, collapsing multipath redundancy and producing intermittent path failures. Setting `arp_ignore` and `arp_announce` to `2` forces each interface to reply and announce only for addresses it actually owns.

See [Network Concepts]({{ site.baseurl }}/common/network-concepts.html) for the detailed explanation.

> **Note:** These settings are only required when the storage NICs share a subnet. If each NIC is on its own dedicated subnet, they are unnecessary (but harmless).

> **⚠️ Interface names in sysctl keys.** A dot in an interface name becomes a forward slash in the sysctl key. A VLAN subinterface `ens1f0np0.2245` is written `net.ipv4.conf.ens1f0np0/2245.arp_ignore`. Getting this wrong fails silently — the key is simply ignored.

**Raw file content for `/etc/sysctl.d/99-iscsi-arp.conf`:**
```
# ARP settings for same-subnet multipath (CRITICAL)
# Prevents ARP responses on wrong interface when multiple NICs share same subnet
# See: Network Concepts documentation for detailed explanation
net.ipv4.conf.all.arp_ignore = 2
net.ipv4.conf.default.arp_ignore = 2
net.ipv4.conf.all.arp_announce = 2
net.ipv4.conf.default.arp_announce = 2

# Interface-specific. Plain interfaces:
net.ipv4.conf.ens1f0.arp_ignore = 2
net.ipv4.conf.ens1f1.arp_ignore = 2
net.ipv4.conf.ens1f0.arp_announce = 2
net.ipv4.conf.ens1f1.arp_announce = 2

# VLAN subinterfaces - the dot becomes a slash:
net.ipv4.conf.ens1f0np0/2245.arp_ignore = 2
net.ipv4.conf.ens1f1np1/2245.arp_ignore = 2
net.ipv4.conf.ens1f0np0/2245.arp_announce = 2
net.ipv4.conf.ens1f1np1/2245.arp_announce = 2
```

Keep only the interface-specific lines that match your actual storage interfaces.

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
    storage:
      files:
        - path: /etc/sysctl.d/99-iscsi-arp.conf
          mode: 0644
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: 99-iscsi-arp.conf content above>"
```

> **How the settings take effect** — the node disruption policy in Step 9 restarts `systemd-sysctl.service`, a oneshot unit that re-reads every file under `/etc/sysctl.d`, so the values apply without a reboot. `sysctl --system` from a debug shell does the same thing by hand if you want to test a value before committing it to a MachineConfig.

> **Verify the settings took effect:**
> ```bash
> oc debug node/<NODE_NAME> -- chroot /host bash -c \
>   'sysctl net.ipv4.conf.all.arp_ignore net.ipv4.conf.all.arp_announce'
> ```
> Both should report `= 2`.

---

## Step 9: Create the Node Disruption Policy

Without a policy, the MCO reboots every worker to apply the MachineConfigs from Steps 4–8. Nothing in them needs a reboot: `iscsid` and `multipathd` re-read their configuration on restart or reload, udev rules and sysctls reload in place, and iface records are read from disk whenever a session is created. This step tells the MCO exactly that.

Create the policy **before** applying any MachineConfig in Step 10. The MCO evaluates it at rollout time, so a policy that lands after a rollout has started does nothing for that rollout.

**Policy file `iscsi-node-disruption-policy.yaml`:**

```yaml
apiVersion: operator.openshift.io/v1
kind: MachineConfiguration
metadata:
  name: cluster
spec:
  nodeDisruptionPolicy:
    files:
      # Step 4 - iscsid reads iscsid.conf only at start-up
      - path: /etc/iscsi/iscsid.conf
        actions:
          - type: Drain
          - type: Restart
            restart:
              serviceName: iscsid.service

      # Step 4 - run the IQN generator, then restart iscsid so it picks up
      # the (possibly new) initiator name
      - path: /usr/local/bin/generate-iscsi-iqn.sh
        actions:
          - type: Drain
          - type: Restart
            restart:
              serviceName: iscsi-initiator-name.service
          - type: Restart
            restart:
              serviceName: iscsid.service

      # Step 5 - "systemctl reload multipathd" is "multipathd reconfigure"
      - path: /etc/multipath.conf
        actions:
          - type: Reload
            reload:
              serviceName: multipathd.service

      # Step 6 - iface records are read from disk when a session is created;
      # a directory path covers every per-NIC file under it
      - path: /var/lib/iscsi/ifaces
        actions:
          - type: None

      # Step 7 - reload the udev rules; new FlashArray devices pick them up
      - path: /etc/udev/rules.d/99-pure-storage.rules
        actions:
          - type: Drain
          - type: Reload
            reload:
              serviceName: systemd-udevd.service

      # Step 8 - systemd-sysctl is a oneshot; restarting it re-applies /etc/sysctl.d
      - path: /etc/sysctl.d/99-iscsi-arp.conf
        actions:
          - type: Restart
            restart:
              serviceName: systemd-sysctl.service

    units:
      - name: multipathd.service
        actions:
          - type: Restart
            restart:
              serviceName: multipathd.service

      - name: iscsid.service
        actions:
          - type: Drain
          - type: Restart
            restart:
              serviceName: iscsid.service

      # New unit file: daemon-reload before systemd can start it, then
      # restart iscsid so the (possibly new) IQN is in use
      - name: iscsi-initiator-name.service
        actions:
          - type: Drain
          - type: DaemonReload
          - type: Restart
            restart:
              serviceName: iscsi-initiator-name.service
          - type: Restart
            restart:
              serviceName: iscsid.service
```

Apply it and confirm the MCO has merged it into the effective cluster policy:

```bash
oc apply -f iscsi-node-disruption-policy.yaml

# Every path and unit from the file above must be listed before you continue
oc get machineconfiguration cluster -o jsonpath='{range .status.nodeDisruptionPolicyStatus.clusterPolicies.files[*]}{.path}{"\n"}{end}{range .status.nodeDisruptionPolicyStatus.clusterPolicies.units[*]}{.name}{"\n"}{end}'
```

The output also lists the cluster's built-in default policies (`/etc/containers/...`, `/var/lib/kubelet/config.json`, and so on); those are expected. If your entries are missing, the policy failed validation — `oc get machineconfiguration cluster -o yaml` shows why under `status.conditions`.

> **Why `Drain` on iscsid and udev?** Restarting `iscsid` does not drop the kernel's iSCSI sessions, and reloading udev does not touch existing devices, so on a worker with no FlashArray volumes yet the drain changes nothing. On a worker that already serves Portworx volumes it is the conservative choice: workloads move before the storage stack is touched, exactly as they would for a reboot, but without the reboot. Drop the `Drain` entries if you would rather apply in place.

> **Why every iscsid restart is paired with the IQN unit.** The MCO builds one action list from every changed file and unit, in an order you do not control, but the actions from a single policy entry stay together and run in the order written. Listing `iscsi-initiator-name.service` immediately before `iscsid.service` in each entry that can change the IQN guarantees `iscsid` restarts after the IQN is final, whichever entry the MCO processes first.

> **⚠️ The policy is all-or-nothing per rollout.** If a MachineConfig update touches even one file or unit that no policy entry covers, the MCO reboots the node for the whole update. That is why Step 2 Option B (NetworkManager connection files) is not in this policy and still reboots the pool — applying network profiles by restarting NetworkManager has not been validated here — and why any file you add to the combined MachineConfig in [Additional Notes](#additional-notes) needs its own entry. The MCO also does not check that the actions you list are sufficient; the checks in Step 10 do.

> **Older clusters.** Node disruption policies are GA in OpenShift 4.17 (Technology Preview in 4.16). On earlier releases the `nodeDisruptionPolicy` field is not recognised; skip this step and expect one rolling reboot in Step 10.

---

## Step 10: Apply the MachineConfigs and Verify the Rollout

With the policy from Step 9 in place, the rollout drains each worker, writes the files, restarts or reloads the listed services, and uncordons the node. No worker reboots.

### Apply

```bash
# Apply all at once - the MCO merges them into one rendered config and rolls each node once
oc apply -f 99-worker-iscsi-network.yaml    # Step 2 Option B only
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
0/N       1/N        0         <- rolling update in progress
N/N       0/N        0         <- complete
```

Wait until `UPDATED=True` and `UPDATING=False` before continuing. Expected steady state:

```
NAME     UPDATED   UPDATING   DEGRADED   MACHINECOUNT   READYMACHINECOUNT   UPDATEDMACHINECOUNT
worker   True      False      False      3              3                   3
```

### Confirm No Node Rebooted

The pool cycles through `UPDATING` exactly as it would for a reboot, so the pool status alone does not tell you which path the MCO took. Check the node events and boot times:

```bash
# One event per action the policy triggered; a node that rebooted shows none of these
oc get events -n default --field-selector involvedObject.kind=Node \
  | grep -E 'SkipReboot|ServiceRestart|ServiceReload'

# The boot time should predate the rollout on every worker
for node in $(oc get nodes -l node-role.kubernetes.io/worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  echo -n "$node: "; oc debug node/$node -q -- chroot /host uptime -s
done
```

Expected events:

```
Normal   ServiceRestart   node/worker-1   Config changes do not require reboot. Service iscsid.service was restarted.
Normal   ServiceReload    node/worker-1   Config changes do not require reboot. Service multipathd.service was reloaded.
```

If a node rebooted instead, see [Nodes Rebooted Despite the Policy](#nodes-rebooted-despite-the-policy). The node is still correctly configured — a reboot applies everything — but fix the policy before the next change.

### Verify Configuration on Every Node

```bash
for node in $(oc get nodes -l node-role.kubernetes.io/worker \
  -o jsonpath='{.items[*].metadata.name}'); do
  echo "=== $node ==="
  oc debug node/$node -- chroot /host bash -c \
    "cat /etc/iscsi/initiatorname.iscsi && systemctl is-active iscsid multipathd"
done
```

**Every node must report a different IQN**, and both `iscsid` and `multipathd` must be `active`. If two nodes still match, the template IQN in Step 4 was wrong — correct it and re-apply.

Further per-node checks:

```bash
oc debug node/<NODE_NAME>
chroot /host

# Verify NIC configuration
nmcli connection show
ip -br addr show

# Verify multipath config and iface bindings
cat /etc/multipath.conf
iscsiadm -m iface

# Check active multipath devices (populated after Portworx creates sessions)
multipath -ll
```

### Verify the Rendered MachineConfig

```bash
# See the merged config the MCO generates for the worker pool
oc get mc rendered-worker-<HASH> -o yaml

# See which MachineConfigs are included
oc get mcp worker -o jsonpath='{.spec.configuration.source}' | jq .
```

---

## Step 11: Install the Portworx Operator

Portworx performs the iSCSI discovery and login and presents FlashArray volumes to pods. Install it after the nodes are prepared, not before.

Create a dedicated namespace for the Portworx cluster components:

```bash
oc create namespace portworx
oc get namespace portworx
```

Then install the **Portworx Certified** operator. From the web console: **Operators → OperatorHub**, search for Portworx, select **Portworx Certified** (published by Everpure, under the Red Hat Certified catalog), set **Installation Mode** to a specific namespace and **Installed Namespace** to `portworx`, then click **Install**.

Or install via OLM subscription into the cluster-wide `openshift-operators` namespace:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: portworx-operator
  namespace: openshift-operators
spec:
  channel: stable
  name: portworx-certified
  source: certified-operators
  sourceNamespace: openshift-marketplace
  installPlanApproval: Automatic
```

```bash
oc apply -f portworx-operator-subscription.yaml
```

Verify the operator pod is running and the CRDs registered:

```bash
oc get pods -n openshift-operators | grep portworx
oc get crd | grep storagecluster
```

Expected:

```
portworx-operator-xxxxxxxxxx-xxxxx   1/1   Running   0   <duration>

purestorageclusters.core.libopenstorage.org   2026-03-22T12:58:39Z
storageclusters.core.libopenstorage.org       2026-03-22T12:58:18Z
```

If the pod is not `Running`, inspect the logs and resolve before continuing:

```bash
oc logs -n openshift-operators deploy/portworx-operator
```

---

## Step 12: Integrate Portworx with FlashArray

### Create a FlashArray API User

On the FlashArray, create a dedicated service account for Portworx with the **Storage Admin** role and generate an API token.

1. Go to: **Settings -> Access -> Users**, create a user (for example `px-portworx`) and assign Storage Admin.
2. Copy and store the API token.

> **⚠️ The API token is shown once.** Store it in your secret manager before closing the dialog.

### Build the pure.json Secret

Create a `pure.json` file containing the FlashArray management endpoint and the token:

```json
{
  "FlashArrays": [
    {
      "MgmtEndPoint": "https://<FLASHARRAY_MGMT_IP_OR_FQDN>",
      "APIToken": "<FLASHARRAY_API_TOKEN>"
    }
  ]
}
```

Create the Kubernetes secret in the same namespace where the StorageCluster will live:

```bash
oc create secret generic px-pure-secret \
  -n portworx \
  --from-file=pure.json=./pure.json

oc get secret px-pure-secret -n portworx
```

> **Note:** For more than one array, add additional entries to the `FlashArrays` list. See the Portworx documentation on multi-array configurations for how StorageClasses then reference an individual array.

---

## Step 13: Deploy the StorageCluster

Generate the spec from [Portworx Central](https://central.portworx.com/specGen/px-csi-specgen) — it produces correctly-annotated YAML for your environment and version, which is easier than hand-writing the annotation and image strings. The example below is for reference.

> **⚠️ `PURE_ISCSI_ALLOWED_IFACES` is what makes multipath work.** It tells Portworx to open iSCSI sessions across **both** storage interfaces simultaneously. Omit it and Portworx uses a single interface, silently giving you one path regardless of how carefully the node was configured in Steps 2 and 6. The interface names must match the iface binding filenames from Step 6 exactly.

```yaml
kind: StorageCluster
apiVersion: core.libopenstorage.org/v1
metadata:
  name: px-cluster-iscsi
  namespace: portworx
  annotations:
    portworx.io/is-openshift: "true"
    portworx.io/misc-args: "--oem px-csi"
spec:
  image: portworx/oci-monitor:<PORTWORX_VERSION>
  imagePullPolicy: Always
  kvdb:
    internal: true
  cloudStorage:
    provider: pure
    deviceSpecs:
      - size=150
    kvdbDeviceSpec: size=32
    systemMetadataDeviceSpec: size=64
  network:
    dataInterface: <NIC1>.<VLAN_ID>
    mgmtInterface: br-ex
  secretsProvider: k8s
  startPort: 17001
  stork:
    enabled: false
  csi:
    enabled: true
  monitoring:
    telemetry:
      enabled: true
    prometheus:
      enabled: true
      exportMetrics: true
  env:
    - name: PURE_FLASHARRAY_SAN_TYPE
      value: "ISCSI"
    - name: PURE_ISCSI_ALLOWED_IFACES
      value: "<NIC1>.<VLAN_ID>,<NIC2>.<VLAN_ID>"
```

Apply it and watch the pods:

```bash
oc apply -f portworx-csi-iscsi.yaml
oc get storagecluster -n portworx
oc get pods -n portworx -w
```

If pods are not progressing to `Running`:

```bash
oc logs -n openshift-operators deploy/portworx-operator
oc logs -n portworx <PORTWORX_POD_NAME>
```

> **⚠️ Do not proceed to StorageClasses or PVCs until the `StorageCluster` is healthy and all Portworx pods in the `portworx` namespace are `Running`.**

---

## Step 14: Create a StorageClass and Validate with a PVC and Pod

Create a StorageClass that uses Portworx as the provisioner and identifies FlashArray as the backend:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: px-pure-iscsi-sc
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"
provisioner: pxd.portworx.com
parameters:
  backend: pure_block
reclaimPolicy: Delete
allowVolumeExpansion: true
volumeBindingMode: WaitForFirstConsumer
```

```bash
oc apply -f flasharray-storageclass.yaml
oc get storageclass
```

> **Note:** You do **not** need `pure_fa_pod_name` or `pure_host_transport` as StorageClass parameters. The transport type is already set on the StorageCluster via `PURE_FLASHARRAY_SAN_TYPE: ISCSI`.

Create a test namespace and PVC:

```bash
oc create namespace px-test
```

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: px-test-pvc
  namespace: px-test
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: px-pure-iscsi-sc
  resources:
    requests:
      storage: 5Gi
```

```bash
oc apply -f px-test-pvc.yaml
oc get pvc px-test-pvc -n px-test -w
```

Expected:

```
NAME          STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS
px-test-pvc   Bound    pvc-08a9597a-d1db-49a5-930a-670ac895cc95   5Gi        RWO            px-pure-iscsi-sc
```

> **Note:** With `volumeBindingMode: WaitForFirstConsumer` the PVC stays `Pending` until a pod schedules against it. That is expected — create the pod below and it will bind.

Mount it in a pod and confirm I/O:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: px-test-pod
  namespace: px-test
spec:
  containers:
    - name: app
      image: registry.access.redhat.com/ubi9/ubi-minimal
      command: ["sleep", "3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: px-test-pvc
```

```bash
oc apply -f px-test-pod.yaml
oc get pod px-test-pod -n px-test
oc exec -it px-test-pod -n px-test -- df -h /data
```

Expected:

```
NAME          READY   STATUS    RESTARTS   AGE
px-test-pod   1/1     Running   0          14m

Filesystem                                     Size  Used Avail Use% Mounted on
/dev/mapper/3624a93708eabcb40cc4241b20a3ed51a  4.9G  129M  4.7G   3% /data
```

The `3624a937...` device name confirms the volume is a FlashArray LUN reached through device-mapper multipath. Confirm the path count on the node that scheduled the pod:

```bash
oc debug node/<NODE_NAME> -- chroot /host multipath -ll
```

You should see one path per storage interface, all `active ready running`. A single path means `PURE_ISCSI_ALLOWED_IFACES` (Step 13) or the iface bindings (Step 6) are wrong.

---

## Step 15: Create a Virtual Machine on FlashArray Storage (Optional)

If the cluster runs OpenShift Virtualization, this validates the full stack the way a workload will actually use it.

First confirm the OS template images have imported onto the new StorageClass:

```bash
oc get pvc -n openshift-virtualization-os-images
```

All PVCs should be `Bound` before continuing. If any are still `Pending` or `Importing`, wait for them to finish.

Then, in the OpenShift web console:

1. Go to: **Virtualization -> VirtualMachines**.
2. Click **Create VirtualMachine** in the top right.
3. Select a template from the catalog — CentOS Stream 9 is a convenient test.
4. In the details drawer, click **Customize VirtualMachine** so you can set the StorageClass explicitly for the boot disk.
5. In the customization wizard, set the VM name, CPU, and memory.
6. Click the **Disks** tab. The default root disk is listed.
7. Click the three-dot menu on the root disk and select **Edit**.
8. In the **StorageClass** dropdown, select `px-pure-iscsi-sc`.
9. Click **Create VirtualMachine**. The VM enters **Provisioning** while the PVC is created on the FlashArray and the OS image is copied into it. This takes a minute or two.
10. The VM flips to **Running** when provisioning completes.

Verify from the CLI:

```bash
oc get vm -n <VM_NAMESPACE>
oc get pvc -n <VM_NAMESPACE>
```

The PVC should be `Bound` and backed by a volume on the FlashArray.

---

## Troubleshooting

### MachineConfig Not Applied

```bash
oc get mcp worker
oc get node -o custom-columns=NAME:.metadata.name,STATE:.metadata.annotations."machineconfiguration\.openshift\.io/state"
oc describe machineconfigpool worker | grep -A 10 Degraded
```

### Nodes Rebooted Despite the Policy

The MCO falls back to a reboot when any changed file or unit in the rendered config has no policy entry. The machine-config-daemon on the node logs one `NodeDisruptionPolicy ... found for diff file` line per covered item; a changed item without one is the culprit.

```bash
# Pick the daemon pod running on the node that rebooted
oc get pods -n openshift-machine-config-operator -l k8s-app=machine-config-daemon -o wide
oc logs -n openshift-machine-config-operator <MCD_POD> -c machine-config-daemon \
  | grep -E 'NodeDisruptionPolicy|post config change action'
```

Common causes:

- The policy was applied after the MachineConfigs, or its entries had not yet appeared in `status.nodeDisruptionPolicyStatus` when the rollout started. Re-run the check in Step 9.
- A file or unit with no entry: a Step 2 Option B `.nmconnection` file, an extra file added to the combined MachineConfig, or a renamed unit. Add an entry for it.
- Another MachineConfig landed in the same rendered config with a change that always reboots (kernel arguments, extensions, OS image, FIPS).
- The cluster is older than OpenShift 4.17, where the policy does not exist.

### Service Not Starting After the Rollout

```bash
oc debug node/<NODE_NAME> -- chroot /host journalctl -u iscsid -u multipathd --no-pager -n 50
```

### Duplicate IQNs After the Rollout

Confirm the oneshot unit ran and what it decided:

```bash
oc debug node/<NODE_NAME> -- chroot /host \
  journalctl -u iscsi-initiator-name --no-pager
```

"Existing unique iSCSI IQN retained" on two nodes reporting the *same* IQN means `TEMPLATE_IQN` in Step 4 does not match the value actually on the nodes. Re-run the Step 1 collection loop, correct the script, and re-apply.

### "Session Already Exists" at Boot

Portworx and `iscsid` are both trying to own session login. See the `node.startup` note in Step 4 — changing that value to `manual` is the documented remedy for Portworx-managed clusters.

### Wrong NIC or No Paths

```bash
oc debug node/<NODE_NAME> -- chroot /host bash -c "iscsiadm -m session -P 3"
```

Look for `Iface Name` in the output — it should name your storage interfaces, not `default`. If it says `default`, the iface files from Step 6 did not land or are named inconsistently with `PURE_ISCSI_ALLOWED_IFACES`.

### Only One Path per Volume

Check, in order:

1. `PURE_ISCSI_ALLOWED_IFACES` lists both interfaces (Step 13).
2. Both iface files exist in `/var/lib/iscsi/ifaces/` (Step 6).
3. Both storage IPs can reach TCP 3260 (Step 2).
4. ARP sysctls are `= 2` if the NICs share a subnet (Step 8).

### Traffic Leaving the Wrong Interface / Intermittent Path Loss

Both storage IPs are on one subnet and sessions are not pinned to their NICs. Confirm the bindings rather than adding routing rules:

```bash
# Each session must name a storage interface, never "default"
oc debug node/<NODE_NAME> -- chroot /host bash -c \
  "iscsiadm -m session -P 3 | grep -E 'Iface Name|Iface IPaddress'"

# ARP must not answer for the other NIC's address
oc debug node/<NODE_NAME> -- chroot /host bash -c \
  "sysctl -a 2>/dev/null | grep -E 'arp_ignore|arp_announce'"
```

If sessions report `default`, the Step 6 iface files are missing or misnamed. If ARP values are not `2`, Step 8 did not apply. Fix those two; do not add per-NIC route tables.

### Multipath Not Picking Up iSCSI Devices

```bash
oc debug node/<NODE_NAME> -- chroot /host bash -c "multipath -ll && multipath -v3 2>&1 | head -50"
```

If devices are being blacklisted, adjust the `blacklist` section in `multipath.conf`. Verify `find_multipaths no` is set.

### NIC Configuration Conflict

If a node's NIC already has a NetworkManager connection from DHCP or the installer, a MachineConfig-deployed `.nmconnection` file may conflict:

```bash
oc debug node/<NODE_NAME> -- chroot /host nmcli connection show
```

If duplicate connections exist, remove the old one via a MachineConfig oneshot unit or change the `id` in your connection file.

---

## Additional Notes

### Full Combined MachineConfig Reference

For environments applying everything at once, this single object produces one rollout per node instead of five — one drain and no reboot under the Step 9 policy. It assumes Step 2 Option A (NMState) handled networking. Every path and unit in it has a policy entry; if you add anything else, add a matching entry or the whole object reboots the node.

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
    storage:
      files:
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

        # iSCSI interface binding - NIC 1
        - path: /var/lib/iscsi/ifaces/<NIC1>.<VLAN_ID>
          mode: 0600
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: NIC1 iface>"

        # iSCSI interface binding - NIC 2
        - path: /var/lib/iscsi/ifaces/<NIC2>.<VLAN_ID>
          mode: 0600
          overwrite: true
          contents:
            source: "data:text/plain;charset=utf-8;base64,<BASE64: NIC2 iface>"

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
        - name: iscsid.service
          enabled: true

        - name: multipathd.service
          enabled: true

        # Generate a unique IQN on boot; replace the template IQN if present
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

### Manual Discovery and Login

Portworx performs discovery and login per volume, so these commands are not part of normal operation. They are useful only to prove connectivity by hand before Portworx is installed, or when diagnosing a path problem:

```bash
oc debug node/<NODE_NAME>
chroot /host

iscsiadm -m discovery -t sendtargets -p <FLASHARRAY_ISCSI_IP>
# 10.x.x.x:3260,2137 iqn.2010-06.com.purestorage:flasharray.64724aac22257212
# 10.x.x.x:3260,2137 iqn.2010-06.com.purestorage:flasharray.64724aac22257212

iscsiadm -m node --loginall=automatic
multipath -ll
```

Expected `multipath -ll` output:

```
mpatha (3624a93708eabcb40cc4241b209e0d22b) dm-0 PURE,FlashArray
size=500G features='0' hwhandler='1 alua' wp=rw
`-+- policy='service-time 0' prio=50 status=active
  |- 33:0:0:254 sdb 8:16 active ready running
  |- 34:0:0:254 sdc 8:32 active ready running
```

Log out again before handing the node back to Portworx.

### Bonding Instead of Two Standalone NICs

This guide uses two standalone interfaces because `PURE_ISCSI_ALLOWED_IFACES` lets Portworx manage both paths directly, which gives true per-path redundancy that multipath can see. Bonding the storage NICs also works and sidesteps same-subnet ARP behaviour, but the array then sees a single path per node and you lose per-path failover visibility. Choose one approach per cluster; do not mix them across nodes in the same pool.

---

## Next Steps

- Register every worker node's IQN with the FlashArray and create a host group for the cluster.
- Review [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md) for performance tuning, APD handling, and monitoring guidance that applies equally to RHCOS.
- Configure Portworx monitoring and Prometheus metrics export if you did not enable them in Step 13.
- Set up a non-default StorageClass per workload tier if you need more than one QoS or reclaim policy.

---

## Related Articles

- [RHEL iSCSI Quick Start](../../rhel/iscsi/QUICKSTART.md)
- [RHEL iSCSI Best Practices](../../rhel/iscsi/BEST-PRACTICES.md) — multipath parameters, APD handling, performance tuning
- [OpenShift NFS Quick Start](../nfs/QUICKSTART.md)
- [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md)
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html)
- [Network Concepts]({{ site.baseurl }}/common/network-concepts.html) — ARP flux and same-subnet multipath
- [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array) — Portworx's own host-prep guidance
- [OpenShift MachineConfig documentation](https://docs.openshift.com/container-platform/latest/post_installation_configuration/machine-configuration-tasks.html)
- [OpenShift node disruption policies](https://docs.redhat.com/en/documentation/openshift_container_platform/4.17/html/machine_configuration/machine-config-node-disruption_machine-configs-configure) — what the `MachineConfiguration` policy in Step 9 can and cannot make rebootless
- [OpenShift Machine Config Operator](https://github.com/openshift/machine-config-operator)
- [Kubernetes NMState Operator](https://docs.openshift.com/container-platform/latest/networking/k8s_nmstate/k8s-nmstate-about-the-k8s-nmstate-operator.html)
