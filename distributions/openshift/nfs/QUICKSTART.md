---
layout: default
title: NFS for OpenShift with FlashBlade and FlashArray File Services
---

# NFS for OpenShift with FlashBlade and FlashArray File Services

---

{% include quickstart/disclaimer.md %}

---

## Overview

This guide configures Red Hat OpenShift Container Platform to dynamically provision NFS persistent volumes from Everpure storage using the Portworx CSI (PX-CSI) driver. Two backends are covered, and both are driven by the same driver, the same `px-pure-secret`, and the same `pure.json` file:

{% include quickstart/px-csi-nfs-backends.md %}

The limitations that shape that choice are listed in [Additional Notes](#additional-notes).

> **Note:** For the same procedure on a non-OpenShift cluster, see the [Kubernetes NFS Quickstart](../../kubernetes/nfs/QUICKSTART.md). That guide covers node preparation with a package manager instead of MachineConfig, and uses `kubectl` instead of `oc`.

> **Scope:** This guide covers dynamic NFS provisioning only. FlashArray block volumes (`pure_block`) and manually defined static NFS PersistentVolumes are out of scope. For block connectivity on Red Hat CoreOS, see the [OpenShift iSCSI Quickstart](../iscsi/QUICKSTART.md).

---

## Prerequisites

- A supported Red Hat OpenShift Container Platform cluster with `cluster-admin` access through `oc`.
- The Portworx Operator and a PX-CSI release compatible with your OpenShift version — see [PX-CSI System Requirements](https://docs.portworx.com/portworx-csi/system-requirements) and the [PX-CSI Release Notes](https://docs.portworx.com/portworx-csi/release-notes). The examples here follow PX-CSI 26.2.
- At least one of the following:
  - An Everpure FlashBlade with a data VIP (the NFS endpoint) and a management endpoint. See [FlashBlade File Services](https://support.everpuredata.com/r/flashblade-file-services/flashblade-file-services) and [Portworx CSI — Prepare FlashBlade](https://docs.portworx.com/portworx-csi/install/prepare/flash-blade).
  - An Everpure FlashArray with File Services enabled, a file virtual interface (File VIF), a parent file system, and an NFS policy. See [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services), [Setting Up File Services on FlashArray](https://support.everpuredata.com/r/flasharray-file-services/setting-up-file-services-68d), [Creating a New File Server Using the File Server Wizard](https://support.everpuredata.com/r/flasharray-file-services/creating-a-new-file-server-using-the-file-server-wizard), and [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array).
- An API token on each array for a user with permission to manage the required file objects. The Portworx prepare pages linked above give the exact user and token steps per array.
- A dedicated storage VLAN, with at least two storage NICs per node and a switch pair configured for a port-channel (MLAG or VPC) so the nodes can be bonded. Configured in [Step 1](#step-1-configure-the-storage-network).
- The Kubernetes NMState Operator, used to declare node storage networking on Red Hat CoreOS. Installed in [Step 1](#step-1-configure-the-storage-network); see the [Kubernetes NMState Operator documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.19/html/networking_operators/k8s-nmstate-about-the-k8s-nmstate-operator).
- Every node can reach both the management endpoint and the NFS endpoint of each array over the network, and NFS traffic is permitted by routing and firewall policy. See [PX-CSI System Requirements](https://docs.portworx.com/portworx-csi/system-requirements).
- Every node can resolve the NFS endpoint using its own DNS configuration if you specify a hostname or VIP name rather than an IP address.

> **Important:** NFS mounts happen in the host network and mount namespace on each node, not inside the CSI pod. Cluster DNS (CoreDNS) is not used to resolve the NFS endpoint. Node-level DNS or an IP address is required.

FlashArray File Services and FlashBlade NFS do not require the host multipath and udev configuration that FlashArray block volumes need.

---

## Background

The two backends behave differently in ways that affect design, not just configuration.

**What a PVC creates.** On FlashBlade, each PVC creates its own file system, so quota and snapshot behavior is per volume. On FlashArray File Services, each PVC creates a managed directory inside a file system that you pre-create, so capacity is shared across every PVC bound to that file system unless you attach a quota policy.

**Access modes.** FlashBlade supports `ReadWriteOnce`, `ReadWriteMany`, `ReadWriteOncePod`, and `ReadOnlyMany`, with read-only export rules applied for `ReadOnlyMany`. FlashArray File Services supports `ReadWriteMany`.

**Export rules and root squash.** Both arrays enforce root squash by default. A pod that sets `securityContext.fsGroup`, or a workload that changes file ownership, can fail with `permission denied` or `lchown failed` because the squashed root cannot change ownership on the export. The fix differs per backend: on FlashBlade, override the export rules from the storage class; on FlashArray, the NFS policy on the array must allow `no_root_squash` and User Mapping must be disabled.

> **Security warning:** `no_root_squash` lets root on an authorized client act as root on the export. Restrict the export rule or NFS policy to the specific node networks that need it, and use it only where a workload requires it.

**Which NFS version applies.** The array export configuration governs which NFS versions clients may negotiate, and it takes precedence over the storage class `mountOptions`. If the storage class asks for a version the array does not permit, the mount fails. Confirm the enabled versions on the array before setting `nfsvers`.

---

## Step 1: Configure the storage network

Do this before provisioning anything. Changing a node's storage network after workloads hold NFS mounts means draining those workloads first.

{% include quickstart/nfs-lacp-topology.md %}

### LACP performance limitations

{% include quickstart/nfs-lacp-limitations.md %}

### Install the Kubernetes NMState Operator

Red Hat CoreOS nodes are immutable, so storage networking is declared through the Kubernetes NMState Operator rather than configured by hand. Install the operator and create its `NMState` instance before applying any policy. Red Hat's [Kubernetes NMState Operator documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.19/html/networking_operators/k8s-nmstate-about-the-k8s-nmstate-operator) is authoritative — change the version in that URL to match your cluster.

> **Important:** Red Hat supports this operator in production on bare metal, IBM Power, IBM Z, IBM LinuxONE, VMware vSphere, and Red Hat OpenStack Platform. On Microsoft Azure, support is limited to configuring DNS servers as a postinstallation task, so the bond layout in this guide is not a supported NMState use case there.

> **Note:** The operator configures secondary NICs. It cannot reconfigure the node's primary NIC, and on most on-premise networks it cannot update the `br-ex` bridge. This suits a dedicated storage network, where the bonded NICs are secondary — do not attempt to bond the primary interface, and do not change `br-ex` or its underlying interfaces after installation.

Installing from the web console:

1. Select **Operators > OperatorHub**.
2. In the search field below **All Items**, enter `nmstate` and press Enter.
3. Select the **Kubernetes NMState Operator** result, click **Install**, then **Install** again to accept the defaults.
4. When the install finishes, click **View Operator**.
5. Under **Provided APIs**, click **Create Instance**.
6. In the **Name** field, confirm the instance name is `nmstate`, then click **Create**.

> **Important:** The instance must be named `nmstate`. It is a cluster-wide singleton and the name restriction is a known issue — an instance under any other name does not take effect.

Installing from the CLI:

```bash
# 1. Operator namespace
cat << EOF | oc apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: openshift-nmstate
spec:
  finalizers:
  - kubernetes
EOF

# 2. OperatorGroup
cat << EOF | oc apply -f -
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: openshift-nmstate
  namespace: openshift-nmstate
spec:
  targetNamespaces:
  - openshift-nmstate
EOF

# 3. Subscription
cat << EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: kubernetes-nmstate-operator
  namespace: openshift-nmstate
spec:
  channel: stable
  installPlanApproval: Automatic
  name: kubernetes-nmstate-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
EOF
```

Confirm the `ClusterServiceVersion` reports `Succeeded` before creating the instance:

```bash
oc get clusterserviceversion -n openshift-nmstate \
  -o custom-columns=Name:.metadata.name,Phase:.status.phase
```

Then create the singleton instance the operator watches for. Without this resource the operator installs but never deploys its node handlers, and any policy you apply is silently ignored:

```bash
cat << EOF | oc apply -f -
apiVersion: nmstate.io/v1
kind: NMState
metadata:
  name: nmstate
EOF
```

Wait for it to become available, then confirm the handler pods are running:

```bash
oc wait --for=condition=Available nmstate/nmstate --timeout=600s
oc get pod -n openshift-nmstate
oc get crd | grep nmstate
```

Every pod should be `Running`, and `nodenetworkconfigurationpolicies.nmstate.io`, `nodenetworkconfigurationenactments.nmstate.io`, and `nodenetworkstates.nmstate.io` should all be registered — those are what the next section applies against. `oc get nns` then lists one `NodeNetworkState` per node reporting the interfaces the operator currently sees, which is also the fastest way to read the real NIC names for the bond.

> **Tip:** If the operator has trouble with its DNS health check probe because of cluster DNS connectivity, add a probe host to the instance — set `spec.probeConfiguration.dns.host` (for example `redhat.com`) on the `NMState` resource and reapply it.

### Apply the bond with NMState

Because each node needs a unique storage IP, create one `NodeNetworkConfigurationPolicy` per node.

```yaml
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: storage-nfs-worker-1        # one NNCP per node
spec:
  nodeSelector:
    kubernetes.io/hostname: <worker-1-hostname>
  desiredState:
    interfaces:
      - name: bond0
        type: bond
        state: up
        mtu: 9000
        link-aggregation:
          mode: 802.3ad
          options:
            miimon: "100"
            lacp_rate: fast
            xmit_hash_policy: layer3+4
          port:
            - <nic1>
            - <nic2>
        ipv4:
          enabled: false            # the VLAN interface carries the address
        ipv6:
          enabled: false
      - name: bond0.<vlan-id>
        type: vlan
        state: up
        mtu: 9000
        vlan:
          base-iface: bond0
          id: <vlan-id>
        ipv4:
          enabled: true
          dhcp: false
          address:
            - ip: <worker-1-storage-ip>
              prefix-length: <prefix>
        ipv6:
          enabled: false
```

The options that matter, and why:

| Setting | Value | Why |
|---|---|---|
| `mode` | `802.3ad` | LACP. Negotiates the aggregation with the switch instead of assuming it. |
| `xmit_hash_policy` | `layer3+4` | Puts ports in the hash so separate TCP connections can use different links. The default `layer2` pins all traffic to one array VIP onto a single link. |
| `lacp_rate` | `fast` | LACPDUs every second rather than every 30, so link loss is detected in about 3 seconds instead of 90. |
| `miimon` | `100` | Link-state polling interval in milliseconds. |
| `mtu` | `9000` | Jumbo frames on the bond and the VLAN interface. Must match end to end — node, both switches, and the array. |

> **Note:** `link-aggregation.port` is the current key for bond members and is what `nmstate.io/v1` expects. Older material — including OpenShift 4.8-era documentation — uses `slaves` for the same field. If you are adapting an older example, rename it to `port`. Bond `options` values are strings, so quote numerics such as `miimon: "100"`.

### Make sure NFS actually uses the storage network

{% include quickstart/nfs-endpoint-reachability.md %}

If your NFS endpoint is on the storage subnet, there is nothing to add — skip to the next section.

If it is on another subnet reached through a router on the storage VLAN, add a route per endpoint to the same `NodeNetworkConfigurationPolicy` that defines the interface. Keep it in one policy: two policies touching the same interface race, and NMState has no ordering between them.

```yaml
apiVersion: nmstate.io/v1
kind: NodeNetworkConfigurationPolicy
metadata:
  name: storage-nfs-worker-1
spec:
  nodeSelector:
    kubernetes.io/hostname: <worker-1-hostname>
  desiredState:
    interfaces:
      # ... the bond and VLAN interfaces from above, unchanged ...
    routes:
      config:
        - destination: <nfs-endpoint>/32
          next-hop-address: <storage-subnet-router>
          next-hop-interface: bond0.<vlan-id>
```

Use a host route (`/32`) per endpoint rather than a route for the endpoint's whole subnet. A subnet route also moves the array's *management* traffic off the default path, and PX-CSI uses that path for its control plane. Keep the data path precise and leave the control path alone.

> **Important:** Removing routes from a policy is not the same as deleting them. Dropping a `routes.config` entry from `desiredState` leaves the route in place while the policy still reports `Available` and `SuccessfullyConfigured`. To withdraw a route, keep the entry and mark it `state: absent`:
>
> ```yaml
>     routes:
>       config:
>         - destination: <nfs-endpoint>/32
>           next-hop-address: <storage-subnet-router>
>           next-hop-interface: bond0.<vlan-id>
>           state: absent
> ```
>
> Because NMState writes routes into the NetworkManager connection profile, a reboot *reapplies* them rather than clearing them, and deleting them by hand with `ip route del` lasts only until the next reconcile or reboot. `state: absent` is the durable removal.

#### Alternative: the same routes through a MachineConfig

Where node networking is managed by MachineConfig rather than NMState, deliver the routes as a `systemd` oneshot unit instead. This suits clusters that do not run the NMState operator.

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-nfs-storage-route
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    systemd:
      units:
        - name: nfs-storage-route.service
          enabled: true
          contents: |
            [Unit]
            Description=Pin NFS traffic to the storage NIC
            After=NetworkManager-wait-online.service network-online.target
            Wants=NetworkManager-wait-online.service network-online.target
            PartOf=network-online.target

            [Service]
            Type=oneshot
            RemainAfterExit=yes
            # `replace` rather than `add`, so a re-run is not an error
            ExecStart=/sbin/ip route replace <nfs-endpoint>/32 \
              via <storage-subnet-router> dev bond0.<vlan-id>

            [Install]
            WantedBy=multi-user.target
```

Two trade-offs to weigh against the NMState form:

- **It reboots the node.** The MCO drains and reboots for a `systemd` unit change, and the pool rolls one node at a time. The NMState policy applies with no reboot.
- **Do not use a NetworkManager keyfile for an interface NMState already owns.** NMState writes its own connection profile; a second profile for the same interface gives NetworkManager two candidates and it may activate the wrong one. A oneshot unit does not compete for ownership.

### Configure the switch and array sides

- Create a matching port-channel on the switch pair, with LACP active and the same hash policy family. A bond spanning two switches requires MLAG, VPC, or the vendor equivalent.
- Put the storage VLAN and MTU 9000 on the port-channel and on the array-facing ports.
- On FlashBlade, confirm the data VIP is in the storage subnet. Where sustained throughput must exceed one member link, add data VIPs rather than widening the bond.
- On FlashArray, confirm the File VIF is in the storage subnet and reachable from the node subnet.

### Verify

```bash
oc get nncp
oc get nnce

# Bond formed, correct mode and hash policy, both links up
oc debug node/<worker> -- chroot /host bash -c 'cat /proc/net/bonding/bond0'

# Addresses and MTU on the bond and VLAN interface
oc debug node/<worker> -- chroot /host bash -c 'ip -d link show bond0; ip addr show bond0.<vlan-id>'

# Which interface will NFS actually leave by — run this before trusting any of the above
oc debug node/<worker> -- chroot /host bash -c 'ip route get <nfs-endpoint>'

# Jumbo frames end to end — fails if any hop is not at 9000
oc debug node/<worker> -- chroot /host bash -c 'ping -M do -s 8972 -c 3 <nfs-endpoint>'
```

Every NNCP should report `Available` and every NNCE `Succeeded`. In `/proc/net/bonding/bond0`, confirm `Bonding Mode: IEEE 802.3ad Dynamic link aggregation`, `Transmit Hash Policy: layer3+4`, both member interfaces with `MII Status: up`, and a populated partner MAC on each — an empty or all-zero partner MAC means the switch is not running LACP on that port and the bond is not actually aggregated.

`ip route get <nfs-endpoint>` must name the VLAN interface and the node's storage address — for example `via <router> dev bond0.<vlan-id> src <worker-1-storage-ip>`. If it names the primary interface or `br-ex` instead, NFS will mount over the management network no matter how healthy the bond looks, and every other check in this section will still pass. Fix that before moving on.

> **Tip:** These commands quote awkwardly. `oc debug ... -- chroot /host bash -c '...'` nests a shell inside a shell, and a redirect such as `</dev/tcp/...` inside the inner quotes is a common source of syntax errors — particularly from PowerShell, or from Git Bash, which also rewrites `/host` into a Windows path. If a command fails with `unexpected end of file` rather than a network error, suspect the quoting, not the cluster. For anything longer than one command, put it in a script file and pipe it in.

The `ping -M do -s 8972` test sets the do-not-fragment bit with a payload that exactly fills a 9000-byte frame. If it fails while a smaller size succeeds, something in the path is still at 1500 and NFS will suffer badly under load rather than fail outright.

---

## Step 2: Prepare the FlashBlade

Skip this step if you are only using FlashArray File Services.

1. In the FlashBlade management interface, go to **Settings > Access** and create a user, then generate an API token for it. Record the token for `pure.json`.
2. Go to **Settings > Network** and record the management endpoint (a virtual interface, named with a `vir` prefix) and the data VIP you will use as the NFS endpoint.
3. Confirm which NFS versions are enabled for the file systems PX-CSI will create. PX-CSI creates the file system per PVC, so the version support comes from the FlashBlade configuration and the export policy rather than from anything you pre-create.

PX-CSI creates the export policy for each provisioned file system. The defaults allow all clients and enforce root squash, and both are overridable from the storage class in [Step 7](#step-7-create-the-flashblade-storageclass).

For multi-tenant deployments using FlashBlade Realms, create a realm user with the appropriate management access policy instead of an array-wide user. Realms require PX-CSI 26.2.0 or later and Purity//FB 4.6.1 or later.

---

## Step 3: Prepare FlashArray File Services

Skip this step if you are only using FlashBlade.

Unlike FlashBlade, the FlashArray objects must exist before the first PVC is provisioned. PX-CSI creates only the managed directory and its export.

{% include quickstart/fa-file-array-requirements.md %}

Record as you go, because the storage class and `pure.json` both reference them by name:
the management endpoint, the File VIF address, the parent file system name, the NFS policy
name, the quota policy name, and a Storage Admin API token.

If your workloads set `fsGroup` or change ownership, disable NFS User Mapping and configure `no_root_squash` in the NFS policy for the authorized node networks.

> **Important:** FlashArray realms do not provide secure multitenancy for FlashArray File Services. Use an account and API token that can manage the required file-service objects directly.

---

## Step 4: Create pure.json and the px-pure-secret

{% include quickstart/px-csi-pure-json.md %}

Create the secret in the namespace where PX-CSI is or will be installed:

```bash
export PX_NAMESPACE=portworx

oc create namespace "${PX_NAMESPACE}" --dry-run=client -o yaml | oc apply -f -

oc create secret generic px-pure-secret \
  --namespace "${PX_NAMESPACE}" \
  --from-file=pure.json=./pure.json

oc get secret px-pure-secret --namespace "${PX_NAMESPACE}"

rm -f ./pure.json
```

---

## Step 5: Install or verify PX-CSI

If PX-CSI is not installed, generate an installation specification through [Portworx Central](https://central.portworx.com/). Select Red Hat OpenShift as the distribution and File as the access type, then install the Portworx Operator and apply the generated `StorageCluster`.

> **Important:** Choosing File as the access type matters beyond the storage classes it creates. A spec generated with a SAN type carries `PURE_FLASHARRAY_SAN_TYPE` in the `StorageCluster` environment, and the node plugin then validates the **block** transport at startup — even on a cluster that only ever uses NFS. Without `/etc/multipath.conf` and `iscsiadm` on every node it exits fatally:
>
> ```
> /etc/multipath.conf not found → Failed to validate multipath configuration → [FATAL]
> Failed to initialize iSCSI interfaces: failed to list iscsi ifaces: exit status 127
> ```
>
> The node pods then `CrashLoopBackOff` and the `StorageCluster` reports `Degraded`, while PVCs still provision on the array and no pod can mount one. Check with:
>
> ```bash
> oc get storagecluster -n "${PX_NAMESPACE}" -o jsonpath='{.items[0].spec.env}{"\n"}'
> ```
>
> A File-only spec omits that variable, and NFS then needs no multipath or iSCSI configuration at all. A cluster that also serves FlashArray block volumes does need the SAN type — and therefore the block host preparation — so do not remove it from an existing cluster to simplify the NFS path.

Verify the deployment:

```bash
oc get storagecluster --namespace "${PX_NAMESPACE}"
oc get pods --namespace "${PX_NAMESPACE}" -o wide
oc get csidriver
oc get storageclass
```

The `StorageCluster` should be online, the controller and node pods should be running, and `pxd.portworx.com` should appear as a CSI driver. PX-CSI creates default storage classes for the backends it discovers.

---

## Step 6: Confirm NFS client support on the nodes

Red Hat CoreOS includes the NFS client, so no package installation is required for a standard NFSv3 or NFSv4.1 mount. Confirm that a node can reach the NFS endpoint before provisioning:

```bash
oc debug node/<node-name> -- chroot /host /bin/bash -c \
  'ping -c 3 <nfs-endpoint>; timeout 3 bash -c "</dev/tcp/<nfs-endpoint>/2049" && echo "port 2049 open"'
```

NFS over TLS is different: it needs a package that RHCOS does **not** ship. The RHEL 9.6
or later base that OpenShift 4.19 and above provide satisfies the kernel side, but
`ktls-utils` — the package supplying the `tlshd` handshake daemon — is absent from the
RHCOS image and is not one of the supported RHCOS extensions. Adding it means layering a
custom RHCOS image and rebooting the node, which is a separate procedure — see
[Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md). Only NFSv3 and
NFSv4.1 without TLS work with no node changes.

---

## Step 7: Create the FlashBlade StorageClass

Skip this step if you are only using FlashArray File Services.

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: fb-nfs
provisioner: pxd.portworx.com
parameters:
  backend: "pure_file"
  pure_export_rules: "*(rw)"
  # pure_nfs_endpoint: "<fb-data-vip>"   # only if it differs from pure.json
reclaimPolicy: Delete
mountOptions:
  - nfsvers=3
  - tcp
allowVolumeExpansion: true
```

Apply and verify:

```bash
oc apply -f fb-nfs.yaml
oc get storageclass fb-nfs -o yaml
```

Parameters worth knowing:

{% include quickstart/px-csi-flashblade-sc-params.md %}

**FlashBlade//EXA** is provisioned differently: it requires a node group and NFSv4.1, and disables NFSv3.

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: fb-exa-nfs
provisioner: pxd.portworx.com
parameters:
  backend: "pure_file"
  pure_fb_node_group: "<node-group>"
  pure_export_rules: "*(rw,no_root_squash)"
  pure_fb_nfsv3_enabled: "false"
  pure_fb_nfsv4_1_enabled: "true"
  pure_fb_snapshot_directory_enabled: "false"
  pure_fb_hard_limit_enabled: "false"
  pure_fb_fast_remove_directory_enabled: "true"
mountOptions:
  - nfsvers=4.1
  - nconnect=16
allowVolumeExpansion: true
```

> **Note:** The Portworx storage class example for a standard FlashBlade uses `nfsvers=3`, while FlashBlade//EXA requires `nfsvers=4.1`. Do not raise a standard FlashBlade class to `nfsvers=4.1` without first confirming that NFSv4.1 is enabled on the array, because the export configuration takes precedence and the mount will otherwise fail. On FlashBlade//EXA, the PVC size is used for validation only — capacity is governed by the node group.

### Using more than one bonded link

{% include quickstart/nfs-nconnect-storageclass.md %}

See [LACP performance limitations](#lacp-performance-limitations) in [Step 1](#step-1-configure-the-storage-network) for why a single-connection mount cannot exceed one member link regardless of bond width.

---

## Step 8: Create the FlashArray File StorageClass

Skip this step if you are only using FlashBlade. The referenced NFS policy and file system must already exist from [Step 3](#step-3-prepare-flasharray-file-services).

```yaml
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: fa-file-rwx
provisioner: pxd.portworx.com
parameters:
  backend: "pure_fa_file"
  pure_nfs_policy: "<nfs-policy>"          # must already exist on the array
  pure_fa_file_system: "<fa-file-system>"  # must already exist on the array
  pure_quota_policy: "<quota-policy>"      # optional; no size limit if omitted
  # pure_nfs_endpoint: "<fa-file-vif>"     # only if the array has several endpoints
mountOptions:
  - nfsvers=4.1
  - proto=tcp
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

Apply and verify:

```bash
oc apply -f fa-file-rwx.yaml
oc get storageclass fa-file-rwx -o yaml
```

> **Capacity warning:** Without `pure_quota_policy`, the PVC request size is not enforced at all — it is advisory. A 1Gi claim will accept far more than 1Gi without error, and the managed directory grows into whatever capacity remains in the parent file system, shared with every other PVC bound to it. The pod cannot see its own limit either: `df` inside the container reports the whole file system, so neither the application nor an operator reading `df` gets any warning before the parent fills. Attach a quota policy on any class used by more than one team or workload.

> **Note:** The Portworx documentation describes NFSv4.1 over TCP as the default for this backend while its storage class example shows `nfsvers=3`. Use `nfsvers=4.1` as above, but verify that the NFS policy you referenced permits NFSv4.1 — the policy on the array wins over the storage class.

### Targeting one array when `pure.json` holds several

{% include quickstart/px-csi-array-id.md %}

If you enable CSI topology, `volumeBindingMode: WaitForFirstConsumer` is required, and `allowedTopologies` must match exactly one array from `pure.json`. A topology expression that matches more than one array fails provisioning. Check whether topology is actually available before relying on it — the driver must advertise topology keys:

```bash
oc get csinode <node> -o jsonpath='{.spec.drivers[?(@.name=="pxd.portworx.com")].topologyKeys}{"\n"}'
```

An empty result (`null`) means CSI topology is not enabled and `allowedTopologies` will not work. Use `portworx.io/pure-array-id` instead.

---

## Step 9: Provision and validate a claim

Create a PVC and a pod that mounts it. This example targets the FlashBlade class; substitute `fa-file-rwx` to validate FlashArray File Services.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nfs-test
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: fb-nfs
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: Pod
metadata:
  name: nfs-test
spec:
  securityContext:
    fsGroup: 2000
  containers:
    - name: writer
      image: registry.access.redhat.com/ubi9/ubi-minimal
      command: ["/bin/sh", "-c", "echo hello > /data/test.txt && sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: nfs-test
```

Apply and verify:

```bash
oc apply -f nfs-test.yaml
oc wait --for=condition=Ready pod/nfs-test --timeout=180s
oc get pvc nfs-test
oc get pod nfs-test -o wide
oc exec nfs-test -- cat /data/test.txt
oc exec nfs-test -- mount | grep ' /data '
```

The PVC should be `Bound`, the pod should be `Running`, `cat` should return `hello`, and the `mount` output should show the NFS endpoint and the negotiated NFS version. On the array, confirm that a FlashBlade file system, or a FlashArray managed directory and its export, now exists for the volume.

> **Note:** On OpenShift, the default restricted SCC assigns an arbitrary UID. Setting `fsGroup` as shown is what makes the mount writable for most workloads — and it is also what makes root squash a problem. If the pod cannot write, treat it as an export-rule or User Mapping issue before suspecting the driver.

> **Note:** This pod triggers Pod Security warnings on a cluster enforcing `restricted` (`allowPrivilegeEscalation`, `capabilities`, `runAsNonRoot`, `seccompProfile`). It is admitted where the namespace only warns, but rejected where `restricted` is enforced. Add the four fields for a namespace that enforces it — and if you add `runAsNonRoot: true`, add `runAsUser` with it. On its own it fails with `container has runAsNonRoot and image will run as root`, because the image's default user is root and the SCC, not the pod spec, is what would otherwise supply a non-root UID.

Clean up the test resources, remembering that a FlashArray managed directory cannot be deleted while it still holds files:

```bash
oc exec nfs-test -- rm -f /data/test.txt
oc delete pod nfs-test
oc delete pvc nfs-test
oc get pv
```

---

## Step 10: Optional — enable NFS over TLS

PX-CSI supports NFS over TLS by adding `xprtsec=tls` to the storage class `mountOptions`:

```yaml
mountOptions:
  - nfsvers=4.1
  - proto=tcp
  - xprtsec=tls
```

{% include quickstart/nfs-tls-requirements.md %}

### Node prerequisite: `ktls-utils` is not in RHCOS

NFS over TLS splits across the kernel and user space, and Red Hat CoreOS ships only the kernel half. `tls.ko` is present; the `tlshd` handshake daemon, from the `ktls-utils` package, is not. Without it the kernel raises a handshake request that nothing answers, so an `xprtsec=tls` mount fails even on a cluster that meets every version requirement.

`ktls-utils` is not an available RHCOS extension either, so closing the gap means layering a custom RHCOS image and rebooting the node — a maintenance window, not a storage class change.

**This is node preparation and it is covered separately.** See [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md) for the RHEL version floor per OpenShift release, both layering paths, and verification. Complete that before continuing here.

Confirm the daemon is in place on a node that will mount the volume:

```bash
oc debug node/<node-name> -- chroot /host bash -c \
  'rpm -q ktls-utils; systemctl is-active tlshd; systemctl is-enabled tlshd'
```

Expect `ktls-utils-<version>`, `active`, and `enabled`. Only once all three hold is `xprtsec=tls` worth adding to a storage class.

> **Important:** Do not check this with `systemctl is-active tlshd` alone. For a unit that does not exist, it prints `inactive` — the same answer it gives for a unit that is installed but stopped. `rpm -q ktls-utils` is the half that distinguishes them.

Also verify the mount option against the [PX-CSI Release Notes](https://docs.portworx.com/portworx-csi/release-notes) for your driver release.

> **Note:** Because the daemon arrives in the boot image, a node that rejoins the pool on an unlayered image loses `tlshd` and stops mounting TLS volumes. Treat the layer as ongoing rather than a one-off task — see [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md).

> **Tip:** The isolated storage VLAN from [Step 1](#step-1-configure-the-storage-network) is the control you already have, and it needs no node changes. Treat it as the baseline and TLS as the addition, not a substitute for it — particularly on a cluster older than 4.19, where the RHCOS base predates RHEL 9.6 and layering will not help.

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| PVC stays `Pending` | Missing or misnamed NFS policy, file system, or quota policy; invalid credentials; unhealthy controller | Run `oc describe pvc <name>`, confirm the objects exist on the array, verify `px-pure-secret`, then check the PX-CSI controller logs. |
| PVC stays `Pending` with a multiple-backends error | More than one FlashArray in `pure.json`. A topology expression can cause it, but two array entries alone are enough — no topology is required to hit this | Set `portworx.io/pure-array-id` on the storage class to the target array's ID from `purearray list`. Note that `pure_nfs_endpoint` does **not** disambiguate backend selection, and `allowedTopologies` only works if CSI topology is enabled. |
| Block (`pure_block`) provisioning breaks after adding a file array to `pure.json` | The new array has no iSCSI configuration for these hosts, so block volumes can no longer resolve a backend: `no IQN or iSCSI portals found for iSCSI transport` | Pin the existing block classes with `portworx.io/pure-array-id` too. Bound volumes keep working, so test by provisioning one new volume per backend after any `pure.json` change. |
| `permission denied` or `lchown failed` | Root squash or NFS User Mapping conflicts with `fsGroup` or an ownership change | On FlashBlade set `pure_export_rules` with `no_root_squash`; on FlashArray disable User Mapping and allow `no_root_squash` in the NFS policy, scoped to the node networks. |
| Mount timeout, or no route to host | NFS endpoint unreachable, routing or firewall block, or DNS failure on the node | Find the node with `oc get pod -o wide`, then test reachability to port 2049 from that node as shown in [Step 6](#step-6-confirm-nfs-client-support-on-the-nodes). |
| Mount fails, often reported as `No such file or directory` / `reason given by server` rather than a version error | The storage class requests an NFS version the array export does not permit. An export published only for NFSv3 is simply absent from the NFSv4.1 pseudo-filesystem, so the client gets ENOENT rather than a version complaint | Align `nfsvers` with the versions enabled on the array — the array configuration takes precedence. Check the policy with `purepolicy nfs list`. Do not be misled into hunting for a wrong path or a deleted directory. |
| Requested PVC size is not enforced | FlashArray File Services class has no quota policy | Create a FlashArray quota policy and reference it with `pure_quota_policy`. |
| PV stays `Released`, or deletion fails | A FlashArray managed directory still contains files | Preserve anything needed, remove the files, then retry the deletion. |
| A newly added array is not discovered | The CSI components have not reloaded the secret | Confirm the `pure.json` content in the secret, then restart the Portworx pods in the PX-CSI namespace. |
| Throughput plateaus at one NIC's line rate | Single TCP connection pinned to one bond member, or `xmit_hash_policy` left at `layer2` | Confirm `Transmit Hash Policy: layer3+4` in `/proc/net/bonding/bond0`, then add `nconnect` to the storage class `mountOptions`. See [LACP performance limitations](#lacp-performance-limitations). |
| Bond is up but never aggregates, or links flap | No matching switch port-channel, or a cross-switch bond without MLAG/VPC | Check for a populated partner MAC per member in `/proc/net/bonding/bond0`; an all-zero partner MAC means the switch side is not running LACP. |
| Small I/O works, large transfers stall or crawl | MTU mismatch somewhere in the path | Run `ping -M do -s 8972` to the NFS endpoint from the node. If it fails, align MTU 9000 across the node, both switches, and the array. |
| Everything reports healthy, but throughput and failover behave like the management network | The storage subnet is link-scoped and the NFS endpoint is on another subnet, so the kernel fell back to the default route | Run `oc debug node/<worker> -- chroot /host ip route get <nfs-endpoint>`. If it names `br-ex` or the primary interface, either move the endpoint onto the storage subnet or add a host route to the NNCP as shown in [Step 1](#step-1-configure-the-storage-network). Do not diagnose this with `ping -I <address>`, which sets only the source address. |
| A route removed from an NNCP is still in the kernel table | Dropping a `routes.config` entry does not withdraw the route, and the policy still reports `Available` | Keep the entry and set `state: absent`. A reboot reapplies the route from the NetworkManager profile rather than clearing it, and `ip route del` lasts only until the next reconcile. See [Step 1](#step-1-configure-the-storage-network). |
| NNCP stays `Progressing` or reports failure | Wrong NIC names, a member NIC already in use, or `slaves` used instead of `port` from an older example | Run `oc get nnce` and inspect the failing enactment. Read real NIC names with `oc get nns <node> -o yaml`. |
| NNCP is accepted but nothing changes on the nodes | No `NMState` instance, or one created under a name other than `nmstate`, so no node handlers are running | Run `oc get nmstate`; the singleton must be named `nmstate`. Recreate it with that name and confirm the pods in `openshift-nmstate` are `Running`. |
| Bond cannot be created on the intended NICs | The policy targets the node's primary NIC, which the operator cannot reconfigure | Bond secondary NICs on a dedicated storage network. Read what each node actually presents with `oc get nns <node> -o yaml`. |
| Mounts work until `xprtsec=tls` is added, failing with `access denied by server` | Most often the node does not trust the array's NFS TLS certificate signer — not an export-rule problem, despite the wording. Also possible: `ktls-utils` absent, `tlshd` not enabled, or array Purity below the TLS floor | Check `journalctl -u tlshd` first: `Certificate signer not found` means a trust-anchor problem, fixed with `x509.truststore` under `[authenticate.client]` in `/etc/tlshd.conf`. Only then check `rpm -q ktls-utils` and the Purity version. See [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md). |
| `xprtsec=tls` worked, then stopped after a node replacement or cluster upgrade | The node booted an unlayered RHCOS image, so `tlshd` is gone | Confirm the pool is still on the layered image with `oc get mcp`. See [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md). |

---

## Additional Notes

**FlashArray File Services limitations.**

{% include quickstart/px-csi-fa-file-limitations.md %}

**Capacity accounting differs by backend.** A FlashBlade PVC maps to its own file system, so the PVC size is the file system size. A FlashArray File Services PVC maps to a directory sharing the parent file system's capacity, so without a quota policy the requested size is advisory only.

**Node-level DNS.** Because the mount happens in the host namespace, an NFS endpoint given as a hostname must resolve through each node's own resolver. An IP address removes this dependency entirely and is the safer choice for a first deployment.

**Version compatibility moves.** The array-side and driver-side floors quoted here — PX-CSI 26.2 for FlashBlade Realms, Purity//FB 4.6.1 for Realms, Purity//FA 6.10.6 and Purity//FB 4.6.0 for NFS over TLS — reflect the PX-CSI 26.2 documentation. Confirm against the current Portworx support matrix before deploying. The client-side floor for NFS over TLS is RHEL 9.6, which is a Red Hat support statement rather than a Portworx one, so the two must be checked separately. Treat the version floor and the package delivery as separate gates as well: clearing RHEL 9.6 says the kernel supports TLS, not that `tlshd` is on the node. On RHCOS it is not, and closing that gap is a layered image and a reboot rather than a version check.

**Storage classes created for you.** PX-CSI provisions default storage classes for the backends it discovers. Review them with `oc get storageclass` before adding your own so you do not end up with duplicates that differ only in mount options.

---

## Next Steps

- Set a cluster default storage class if NFS should be the default for unqualified PVCs.
- Create one storage class per service tier rather than per workload, so mount options and export rules stay reviewable.
- Attach quota policies to every FlashArray File Services class that more than one team consumes.
- Decide how RWX file data is protected, given that the `pure_fa_file` backend cannot be snapshotted through the driver.
- NFS over TLS on OpenShift 4.19 and later clears the RHEL 9.6 kernel-side floor, but `ktls-utils` is not in RHCOS and is not an available extension, so it needs a layered image and a rolling reboot. Budget a maintenance window rather than treating TLS as a storage class change, and keep the layer in place so replacement nodes inherit `tlshd` — see [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md).

---

## Related Articles

- [Installing ktls-utils on Red Hat CoreOS](../nfs-tls/QUICKSTART.md) — the node preparation required before `xprtsec=tls` mounts will work
- [Kubernetes NFS Quickstart](../../kubernetes/nfs/QUICKSTART.md) — the same two backends on a non-OpenShift cluster
- [OpenShift iSCSI Multipathing and NIC Binding via MachineConfig](../iscsi/QUICKSTART.md) — block connectivity on Red Hat CoreOS worker nodes
- [NFS on RHEL Quickstart](../../rhel/nfs/QUICKSTART.md) — host-level NFS mounts and the underlying mount options
- [NFS on RHEL Best Practices](../../rhel/nfs/BEST-PRACTICES.md) — NFS tuning, `nconnect`, and failover behavior
- [Portworx CSI — Prepare FlashBlade](https://docs.portworx.com/portworx-csi/install/prepare/flash-blade)
- [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array)
- [Portworx CSI — Install PX-CSI](https://docs.portworx.com/portworx-csi/install/install-portworx-csi)
- [Portworx CSI — Dynamic Provisioning of FlashBlade File Systems](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flashblade-file-systems)
- [Portworx CSI — Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services)
- [Portworx CSI — StorageClass Reference](https://docs.portworx.com/portworx-csi/reference/storage-class)
- [Portworx CSI — FlashArray and FlashBlade JSON File Reference](https://docs.portworx.com/portworx-csi/reference/pure-json-reference)
- [Portworx CSI — System Requirements](https://docs.portworx.com/portworx-csi/system-requirements)
- [Portworx CSI — Release Notes](https://docs.portworx.com/portworx-csi/release-notes)
