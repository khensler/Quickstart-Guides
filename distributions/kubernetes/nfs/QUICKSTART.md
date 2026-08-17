---
layout: default
title: NFS for Kubernetes with FlashBlade and FlashArray File Services
---

# NFS for Kubernetes with FlashBlade and FlashArray File Services

---

{% include quickstart/disclaimer.md %}

---

## Overview

This guide configures an upstream Kubernetes cluster to dynamically provision NFS persistent volumes from Everpure storage using the Portworx CSI (PX-CSI) driver. Two backends are covered, and both are driven by the same driver, the same `px-pure-secret`, and the same `pure.json` file:

{% include quickstart/px-csi-nfs-backends.md %}

The limitations that shape that choice are listed in [Additional Notes](#additional-notes).

> **Note:** If your cluster is Red Hat OpenShift, use the [OpenShift NFS Quickstart](../../openshift/nfs/QUICKSTART.md) instead. It is the same procedure, but node preparation goes through MachineConfig rather than a package manager, and it covers the SCC and `fsGroup` behavior specific to OpenShift.

> **Scope:** This guide covers dynamic NFS provisioning through PX-CSI. Statically defined NFS PersistentVolumes and FlashArray block volumes (`pure_block`) are out of scope. For host-level NFS mounts and the reasoning behind the mount options, see the [NFS on RHEL Quickstart](../../rhel/nfs/QUICKSTART.md).

---

## Prerequisites

- A Kubernetes cluster on a version supported by your PX-CSI release, with `cluster-admin` access through `kubectl` — see [PX-CSI System Requirements](https://docs.portworx.com/portworx-csi/system-requirements).
- The Portworx Operator and a compatible PX-CSI release — see the [PX-CSI Release Notes](https://docs.portworx.com/portworx-csi/release-notes). The examples here follow PX-CSI 26.2.
- At least one of the following:
  - An Everpure FlashBlade with a data VIP (the NFS endpoint) and a management endpoint. See [FlashBlade File Services](https://support.everpuredata.com/r/flashblade-file-services/flashblade-file-services) and [Portworx CSI — Prepare FlashBlade](https://docs.portworx.com/portworx-csi/install/prepare/flash-blade).
  - An Everpure FlashArray with File Services enabled, a file virtual interface (File VIF), a parent file system, and an NFS policy. See [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services), [Setting Up File Services on FlashArray](https://support.everpuredata.com/r/flasharray-file-services/setting-up-file-services-68d), [Creating a New File Server Using the File Server Wizard](https://support.everpuredata.com/r/flasharray-file-services/creating-a-new-file-server-using-the-file-server-wizard), and [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array).
- An API token on each array for a user with permission to manage the required file objects. The Portworx prepare pages linked above give the exact user and token steps per array.
- NFS client utilities installed on every node, including control-plane nodes that may run workloads. Installed in [Step 2](#step-2-install-nfs-client-utilities-on-every-node); for the underlying host-side detail see the [NFS on RHEL Quickstart](../../rhel/nfs/QUICKSTART.md).
- A dedicated storage VLAN, with at least two storage NICs per node and a switch pair configured for a port-channel (MLAG or VPC) so the nodes can be bonded. Configured in [Step 1](#step-1-configure-the-storage-network).
- A node kernel of 5.3 or later if you intend to use `nconnect` to spread a mount across bonded links.
- Every node can reach both the management endpoint and the NFS endpoint of each array, and NFS traffic is permitted by routing and firewall policy. See [PX-CSI System Requirements](https://docs.portworx.com/portworx-csi/system-requirements).
- Every node can resolve the NFS endpoint through its own DNS configuration if you specify a hostname or VIP name rather than an IP address.

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

### Apply the bond on each node

Configure the bond with whatever manages node networking in your environment. The three common backends follow — apply the same settings through your configuration management or node image rather than by hand on each node, so replacement nodes inherit them.

NetworkManager, on the RHEL family and SUSE:

```bash
# Bond with LACP, fast rate, and a hash policy that includes ports
nmcli con add type bond ifname bond0 con-name bond0 \
  bond.options "mode=802.3ad,miimon=100,lacp_rate=fast,xmit_hash_policy=layer3+4"

# Enslave both storage NICs
nmcli con add type ethernet ifname <nic1> master bond0 con-name bond0-nic1
nmcli con add type ethernet ifname <nic2> master bond0 con-name bond0-nic2

# Storage VLAN on top of the bond, carrying the node's storage address
nmcli con add type vlan ifname bond0.<vlan-id> con-name storage \
  dev bond0 id <vlan-id> \
  ip4 <node-storage-ip>/<prefix>

# Jumbo frames on the bond and the VLAN interface
nmcli con mod bond0 802-3-ethernet.mtu 9000
nmcli con mod storage 802-3-ethernet.mtu 9000

nmcli con up bond0
nmcli con up storage
```

Netplan, on Ubuntu:

```yaml
network:
  version: 2
  ethernets:
    <nic1>:
      mtu: 9000
    <nic2>:
      mtu: 9000
  bonds:
    bond0:
      interfaces: [<nic1>, <nic2>]
      mtu: 9000
      parameters:
        mode: 802.3ad
        mii-monitor-interval: 100
        lacp-rate: fast
        transmit-hash-policy: layer3+4
  vlans:
    bond0.<vlan-id>:
      id: <vlan-id>
      link: bond0
      mtu: 9000
      addresses: [<node-storage-ip>/<prefix>]
```

systemd-networkd, on Debian cloud images and anywhere NetworkManager is not installed:

```ini
# /etc/systemd/network/10-bond0.netdev
[NetDev]
Name=bond0
Kind=bond
MTUBytes=9000

[Bond]
Mode=802.3ad
TransmitHashPolicy=layer3+4
LACPTransmitRate=fast
MIIMonitorSec=100ms
```

```ini
# /etc/systemd/network/20-bond0-members.network — one file per member, or a glob
[Match]
Name=<nic1> <nic2>

[Link]
MTUBytes=9000

[Network]
Bond=bond0
```

```ini
# /etc/systemd/network/30-bond0-vlan.netdev
[NetDev]
Name=bond0.<vlan-id>
Kind=vlan
MTUBytes=9000

[VLAN]
Id=<vlan-id>
```

```ini
# /etc/systemd/network/40-bond0.network
[Match]
Name=bond0

[Network]
VLAN=bond0.<vlan-id>
```

```ini
# /etc/systemd/network/50-storage.network
[Match]
Name=bond0.<vlan-id>

[Link]
MTUBytes=9000

[Network]
Address=<node-storage-ip>/<prefix>
```

Then `systemctl restart systemd-networkd` and confirm with `networkctl status bond0`.

> **Note:** Debian and Ubuntu cloud images are configured by cloud-init, which writes to whichever backend is present — `systemd-networkd` on a minimal Debian image, Netplan on Ubuntu. Check with `networkctl status` and `nmcli general status` before assuming which of the three recipes applies, and put the result into your node image or configuration management so replacement nodes match.

The options that matter, and why:

| Setting | Value | Why |
|---|---|---|
| `mode` | `802.3ad` | LACP. Negotiates the aggregation with the switch instead of assuming it. |
| `xmit_hash_policy` / `transmit-hash-policy` / `TransmitHashPolicy` | `layer3+4` | Puts ports in the hash so separate TCP connections can use different links. The default `layer2` pins all traffic to one array VIP onto a single link. |
| `lacp_rate` / `lacp-rate` / `LACPTransmitRate` | `fast` | LACPDUs every second rather than every 30, so link loss is detected in about 3 seconds instead of 90. |
| `miimon` / `mii-monitor-interval` / `MIIMonitorSec` | `100` | Link-state polling interval in milliseconds. |
| `mtu` | `9000` | Jumbo frames on the members, the bond, and the VLAN interface. Must match end to end — node, both switches, and the array. |

### Make sure NFS actually uses the storage network

{% include quickstart/nfs-endpoint-reachability.md %}

If your NFS endpoint is on the storage subnet, there is nothing to add. If it is on another subnet reached through a router on the storage VLAN, add a host route per endpoint using the same tool that manages the bond:

```bash
# NetworkManager — persists in the connection profile
sudo nmcli con mod storage +ipv4.routes "<nfs-endpoint>/32 <storage-subnet-router>"
sudo nmcli con up storage

# Verify, and remove again if needed
nmcli -f ipv4.routes con show storage
sudo nmcli con mod storage -ipv4.routes "<nfs-endpoint>/32 <storage-subnet-router>"
```

```yaml
# Netplan — under the VLAN interface
  vlans:
    bond0.<vlan-id>:
      id: <vlan-id>
      link: bond0
      mtu: 9000
      addresses: [<node-storage-ip>/<prefix>]
      routes:
        - to: <nfs-endpoint>/32
          via: <storage-subnet-router>
```

```ini
# systemd-networkd — append to 50-storage.network
[Route]
Destination=<nfs-endpoint>/32
Gateway=<storage-subnet-router>
```

Use a host route (`/32`) per endpoint rather than a route for the endpoint's whole subnet. A subnet route also moves the array's *management* traffic off the default path, and PX-CSI uses that path for its control plane.

> **Important:** Add the route wherever the bond itself is defined — the node image or configuration management — not by hand with `ip route add`. A manual kernel route disappears on the next reboot or network reconcile, and the symptom is NFS quietly reverting to the management path rather than failing outright.

### Configure the switch and array sides

- Create a matching port-channel on the switch pair, with LACP active and the same hash policy family. A bond spanning two switches requires MLAG, VPC, or the vendor equivalent.
- Put the storage VLAN and MTU 9000 on the port-channel and on the array-facing ports.
- On FlashBlade, confirm the data VIP is in the storage subnet. Where sustained throughput must exceed one member link, add data VIPs rather than widening the bond.
- On FlashArray, confirm the File VIF is in the storage subnet and reachable from the node subnet.

### Verify

```bash
# Bond formed, correct mode and hash policy, both links up
cat /proc/net/bonding/bond0

# Addresses and MTU on the bond and VLAN interface
ip -d link show bond0
ip addr show bond0.<vlan-id>

# Which interface will NFS actually leave by — run this before trusting any of the above
ip route get <nfs-endpoint>

# Jumbo frames end to end — fails if any hop is not at 9000
ping -M do -s 8972 -c 3 <nfs-endpoint>
```

In `/proc/net/bonding/bond0`, confirm `Bonding Mode: IEEE 802.3ad Dynamic link aggregation`, `Transmit Hash Policy: layer3+4`, both member interfaces with `MII Status: up`, and a populated partner MAC on each — an empty or all-zero partner MAC means the switch is not running LACP on that port and the bond is not actually aggregated.

`ip route get <nfs-endpoint>` must name the VLAN interface and the node's storage address — for example `via <router> dev bond0.<vlan-id> src <node-storage-ip>`. If it names the node's primary interface instead, NFS will mount over the management network no matter how healthy the bond looks, and every other check in this section will still pass.

The `ping -M do -s 8972` test sets the do-not-fragment bit with a payload that exactly fills a 9000-byte frame. If it fails while a smaller size succeeds, something in the path is still at 1500 and NFS will suffer badly under load rather than fail outright.

---

## Step 2: Install NFS client utilities on every node

Unlike Red Hat CoreOS, a general-purpose Linux node needs the NFS client installed explicitly. Install it on every node that can schedule a pod using this storage, then confirm the client services are enabled.

```bash
# RHEL, Rocky, AlmaLinux, Oracle Linux
sudo dnf install -y nfs-utils
sudo systemctl enable --now nfs-client.target rpcbind

# Debian and Ubuntu
sudo apt-get update
sudo apt-get install -y nfs-common

# SUSE and openSUSE
sudo zypper install -y nfs-client
sudo systemctl enable --now nfs-client.target
```

Verify the client is present and the array is reachable from a node:

```bash
mount.nfs -V
kubectl get nodes -o custom-columns=NAME:.metadata.name,OS:.status.nodeInfo.osImage,KERNEL:.status.nodeInfo.kernelVersion
```

{% include quickstart/nfs-verify-connectivity.md %}

> **Note:** A missing NFS client shows up later as a pod stuck in `ContainerCreating` with a mount error in its events, not as a PVC failure. The PVC binds because provisioning on the array succeeded — only the mount fails. Installing the client everywhere up front avoids chasing that symptom.

---

## Step 3: Prepare the FlashBlade

Skip this step if you are only using FlashArray File Services.

1. In the FlashBlade management interface, go to **Settings > Access** and create a user, then generate an API token for it. Record the token for `pure.json`.
2. Go to **Settings > Network** and record the management endpoint (a virtual interface, named with a `vir` prefix) and the data VIP you will use as the NFS endpoint.
3. Confirm which NFS versions are enabled for the file systems PX-CSI will create. PX-CSI creates the file system per PVC, so version support comes from the FlashBlade configuration and the export policy rather than from anything you pre-create.

PX-CSI creates the export policy for each provisioned file system. The defaults allow all clients and enforce root squash, and both are overridable from the storage class in [Step 7](#step-7-create-the-flashblade-storageclass).

For multi-tenant deployments using FlashBlade Realms, create a realm user with the appropriate management access policy instead of an array-wide user. Realms require PX-CSI 26.2.0 or later and Purity//FB 4.6.1 or later.

---

## Step 4: Prepare FlashArray File Services

Skip this step if you are only using FlashBlade.

Unlike FlashBlade, the FlashArray objects must exist before the first PVC is provisioned. PX-CSI creates only the managed directory and its export.

{% include quickstart/fa-file-array-requirements.md %}

Record as you go, because the storage class and `pure.json` both reference them by name:
the management endpoint, the File VIF address, the parent file system name, the NFS policy
name, the quota policy name, and a Storage Admin API token.

If your workloads set `fsGroup` or change ownership, disable NFS User Mapping and configure `no_root_squash` in the NFS policy for the authorized node networks.

> **Important:** FlashArray realms do not provide secure multitenancy for FlashArray File Services. Use an account and API token that can manage the required file-service objects directly.

---

## Step 5: Create pure.json and the px-pure-secret

{% include quickstart/px-csi-pure-json.md %}

Create the secret in the namespace where PX-CSI is or will be installed:

```bash
export PX_NAMESPACE=portworx

kubectl create namespace "${PX_NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic px-pure-secret \
  --namespace "${PX_NAMESPACE}" \
  --from-file=pure.json=./pure.json

kubectl get secret px-pure-secret --namespace "${PX_NAMESPACE}"

rm -f ./pure.json
```

---

## Step 6: Install or verify PX-CSI

If PX-CSI is not installed, generate an installation specification through [Portworx Central](https://central.portworx.com/). Select **None** as the Kubernetes distribution for an upstream cluster, set your Kubernetes version and namespace, and choose File as the access type. Portworx Central returns two manifest URLs — one for the operator and one for the `StorageCluster`:

```bash
kubectl apply -f '<operator-url-from-portworx-central>'
kubectl apply -f '<storagecluster-url-from-portworx-central>'
```

Verify the deployment:

```bash
kubectl get storagecluster --namespace "${PX_NAMESPACE}"
kubectl get pods --namespace "${PX_NAMESPACE}" -o wide
kubectl get csidriver
kubectl get storageclass
```

The `StorageCluster` should be online, the controller and node pods should be running, and `pxd.portworx.com` should appear as a CSI driver. PX-CSI creates default storage classes for the backends it discovers — review those before adding your own.

> **Note:** Generate the spec rather than hand-writing the `StorageCluster`. The generated manifest carries the image references, RBAC, and namespace wiring that match the PX-CSI version you selected, and getting those wrong is the most common cause of a cluster that installs but never comes online.

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
> kubectl get storagecluster -n "${PX_NAMESPACE}" -o jsonpath='{.items[0].spec.env}{"\n"}'
> ```
>
> A File-only spec omits that variable, and NFS then needs no multipath or iSCSI packages at all. If you do need a SAN type because the cluster also serves block, install the block prerequisites on every node as well.

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
kubectl apply -f fb-nfs.yaml
kubectl get storageclass fb-nfs -o yaml
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

Skip this step if you are only using FlashBlade. The referenced NFS policy and file system must already exist from [Step 4](#step-4-prepare-flasharray-file-services).

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
kubectl apply -f fa-file-rwx.yaml
kubectl get storageclass fa-file-rwx -o yaml
```

> **Capacity warning:** Without `pure_quota_policy`, the PVC request size is not enforced at all — it is advisory. A 1Gi claim will accept far more than 1Gi without error, and the managed directory grows into whatever capacity remains in the parent file system, shared with every other PVC bound to it. The pod cannot see its own limit either: `df` inside the container reports the whole file system, so neither the application nor an operator reading `df` gets any warning before the parent fills. Attach a quota policy on any class used by more than one team or workload.

> **Note:** The Portworx documentation describes NFSv4.1 over TCP as the default for this backend while its storage class example shows `nfsvers=3`. Use `nfsvers=4.1` as above, but verify that the NFS policy you referenced permits NFSv4.1 — the policy on the array wins over the storage class.

### Targeting one array when `pure.json` holds several

{% include quickstart/px-csi-array-id.md %}

If you enable CSI topology, `volumeBindingMode: WaitForFirstConsumer` is required, and `allowedTopologies` must match exactly one array from `pure.json`. A topology expression that matches more than one array fails provisioning. Check whether topology is actually available before relying on it — the driver must advertise topology keys:

```bash
kubectl get csinode <node> -o jsonpath='{.spec.drivers[?(@.name=="pxd.portworx.com")].topologyKeys}{"\n"}'
```

An empty result (`null`) means CSI topology is not enabled and `allowedTopologies` will not work. Use `portworx.io/pure-array-id` instead.

---

## Step 9: Provision and validate a claim

Create a PVC and a pod that mounts it. This example targets the FlashBlade class; substitute `fa-file-rwx` to validate FlashArray File Services. Those classes are the ones defined in [Step 7](#step-7-create-the-flashblade-storageclass) and [Step 8](#step-8-create-the-flasharray-file-storageclass) — replace the names if you did not use the defaults above.

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
kubectl apply -f nfs-test.yaml
kubectl wait --for=condition=Ready pod/nfs-test --timeout=180s
kubectl get pvc nfs-test
kubectl get pod nfs-test -o wide
kubectl exec nfs-test -- cat /data/test.txt
kubectl exec nfs-test -- mount | grep ' /data '
```

The PVC should be `Bound`, the pod should be `Running`, `cat` should return `hello`, and the `mount` output should show the NFS endpoint and the negotiated NFS version. On the array, confirm that a FlashBlade file system, or a FlashArray managed directory and its export, now exists for the volume.

Confirm the RWX behavior that justifies this storage in the first place, by scheduling a second pod on a different node against the same claim. Listing access modes is not the same test — a PV can report `ReadWriteMany` while a second node cannot actually mount it, so schedule the pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nfs-test-b
  labels:
    app: nfs-test-rwx
spec:
  securityContext:
    fsGroup: 2000
  affinity:
    podAntiAffinity:
      # Required, not preferred: on a multi-node cluster this must land elsewhere
      # or the test proves nothing. It stays Pending if it cannot, which is the
      # correct, visible failure.
      requiredDuringSchedulingIgnoredDuringExecution:
        - labelSelector:
            matchLabels:
              app: nfs-test-rwx
          topologyKey: kubernetes.io/hostname
  containers:
    - name: reader-writer
      image: registry.access.redhat.com/ubi9/ubi-minimal
      command:
        - /bin/sh
        - -c
        - |
          set -e
          for i in $(seq 1 60); do [ -f /data/test.txt ] && break; sleep 2; done
          echo "peer wrote: $(cat /data/test.txt)"
          echo "hello-from-b" > /data/test-b.txt
          sleep 3600
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: nfs-test
```

Add the matching `app: nfs-test-rwx` label to the first pod so the anti-affinity rule has something to repel from.

```bash
kubectl apply -f nfs-test-b.yaml
kubectl get pods -o custom-columns=POD:.metadata.name,STATUS:.status.phase,NODE:.spec.nodeName
kubectl logs nfs-test-b
kubectl exec nfs-test -- ls -l /data
```

The two pods must show **different** node names, `kubectl logs nfs-test-b` should print the file the first pod wrote, and `ls -l /data` from the first pod should show `test-b.txt` written by the second. Both pods reading *and* writing is the point: a read-only check would pass even against a read-only export, which is exactly the failure this is meant to rule out.

```bash
kubectl get pv -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,MODES:.spec.accessModes
```

Clean up the test resources, remembering that a FlashArray managed directory cannot be deleted while it still holds files:

```bash
kubectl exec nfs-test -- rm -f /data/test.txt
kubectl delete pod nfs-test
kubectl delete pvc nfs-test
kubectl get pv
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

Check the node OS version first, then install the packages and enable the handshake daemon on every node:

```bash
# Confirm the release is 9.6 or later before going further
cat /etc/redhat-release

sudo dnf install -y nfs-utils ktls-utils openssl
sudo systemctl enable --now tlshd
systemctl status tlshd --no-pager
```

On Debian and Ubuntu, `ktls-utils` availability varies by release and the supported-configuration statement above does not apply. Confirm both before planning a rollout:

```bash
apt-cache policy ktls-utils
```

Add these packages to your node image or configuration management alongside the NFS client from [Step 2](#step-2-install-nfs-client-utilities-on-every-node), so a replacement node does not join without `tlshd` and fail to mount TLS volumes.

Also verify the mount option against the [PX-CSI Release Notes](https://docs.portworx.com/portworx-csi/release-notes) for your driver release.

> **Tip:** Where encryption in flight is a requirement you must satisfy today and your nodes predate RHEL 9.6, the isolated storage VLAN from [Step 1](#step-1-configure-the-storage-network) is the control you already have. Treat it as the baseline and TLS as the addition, not a substitute for it.

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| PVC stays `Pending` | Missing or misnamed NFS policy, file system, or quota policy; invalid credentials; unhealthy controller | Run `kubectl describe pvc <name>`, confirm the objects exist on the array, verify `px-pure-secret`, then check the PX-CSI controller logs. |
| PVC stays `Pending` with a multiple-backends error | More than one FlashArray in `pure.json`. A topology expression can cause it, but two array entries alone are enough — no topology is required to hit this | Set `portworx.io/pure-array-id` on the storage class to the target array's ID from `purearray list`. Note that `pure_nfs_endpoint` does **not** disambiguate backend selection, and `allowedTopologies` only works if CSI topology is enabled. |
| Block (`pure_block`) provisioning breaks after adding a file array to `pure.json` | The new array has no iSCSI configuration for these hosts, so block volumes can no longer resolve a backend: `no IQN or iSCSI portals found for iSCSI transport` | Pin the existing block classes with `portworx.io/pure-array-id` too. Bound volumes keep working, so test by provisioning one new volume per backend after any `pure.json` change. |
| PVC is `Bound` but the pod stays `ContainerCreating` | The NFS client is missing on the scheduled node, or the mount is failing | Run `kubectl describe pod <name>` for the mount error, then confirm the client packages from [Step 2](#step-2-install-nfs-client-utilities-on-every-node) on that node. |
| `permission denied` or `lchown failed` | Root squash or NFS User Mapping conflicts with `fsGroup` or an ownership change | On FlashBlade set `pure_export_rules` with `no_root_squash`; on FlashArray disable User Mapping and allow `no_root_squash` in the NFS policy, scoped to the node networks. |
| Mount timeout, or no route to host | NFS endpoint unreachable, routing or firewall block, or DNS failure on the node | Find the node with `kubectl get pod -o wide`, then test reachability to port 2049 from that node. |
| Mount fails, often reported as `No such file or directory` / `reason given by server` rather than a version error | The storage class requests an NFS version the array export does not permit. An export published only for NFSv3 is simply absent from the NFSv4.1 pseudo-filesystem, so the client gets ENOENT rather than a version complaint | Align `nfsvers` with the versions enabled on the array — the array configuration takes precedence. Check the policy with `purepolicy nfs list`. Do not be misled into hunting for a wrong path or a deleted directory. |
| Requested PVC size is not enforced | FlashArray File Services class has no quota policy | Create a FlashArray quota policy and reference it with `pure_quota_policy`. |
| PV stays `Released`, or deletion fails | A FlashArray managed directory still contains files | Preserve anything needed, remove the files, then retry the deletion. |
| A newly added array is not discovered | The CSI components have not reloaded the secret | Confirm the `pure.json` content in the secret, then restart the Portworx pods in the PX-CSI namespace. |
| Throughput plateaus at one NIC's line rate | Single TCP connection pinned to one bond member, or `xmit_hash_policy` left at `layer2` | Confirm `Transmit Hash Policy: layer3+4` in `/proc/net/bonding/bond0`, then add `nconnect` to the storage class `mountOptions`. See [LACP performance limitations](#lacp-performance-limitations). |
| Everything reports healthy, but throughput and failover behave like the management network | The storage subnet is link-scoped and the NFS endpoint is on another subnet, so the kernel fell back to the default route | Run `ip route get <nfs-endpoint>`. If it names the primary interface, either move the endpoint onto the storage subnet or add a host route as shown in [Step 1](#step-1-configure-the-storage-network). Do not diagnose this with `ping -I <address>`, which sets only the source address. |
| A storage route works, then vanishes after a reboot | The route was added by hand with `ip route add` instead of in the interface configuration | Add it in NetworkManager, Netplan, or systemd-networkd alongside the bond, so it persists and replacement nodes inherit it. |
| Bond is up but never aggregates, or links flap | No matching switch port-channel, or a cross-switch bond without MLAG/VPC | Check for a populated partner MAC per member in `/proc/net/bonding/bond0`; an all-zero partner MAC means the switch side is not running LACP. |
| Small I/O works, large transfers stall or crawl | MTU mismatch somewhere in the path | Run `ping -M do -s 8972` to the NFS endpoint from the node. If it fails, align MTU 9000 across the node, both switches, and the array. |
| `nconnect` missing from a live mount | Node kernel older than 5.3, or the option was added after the volume was mounted | Check `uname -r`, then reschedule the pod so the volume remounts with the current storage class options. |
| Mounts work until `xprtsec=tls` is added, failing with `access denied by server` | Most often the node does not trust the array's NFS TLS certificate signer — not an export-rule problem, despite the wording. Also possible: `tlshd` not running, node OS older than RHEL 9.6, or array Purity below the TLS floor | Check `journalctl -u tlshd` first: `Certificate signer not found` means a trust-anchor problem, fixed with `x509.truststore` under `[authenticate.client]` in `/etc/tlshd.conf`. Only then check `cat /etc/redhat-release`, `systemctl status tlshd`, and the Purity version. |

---

## Additional Notes

**FlashArray File Services limitations.**

{% include quickstart/px-csi-fa-file-limitations.md %}

**Capacity accounting differs by backend.** A FlashBlade PVC maps to its own file system, so the PVC size is the file system size. A FlashArray File Services PVC maps to a directory sharing the parent file system's capacity, so without a quota policy the requested size is advisory only.

**Node-level DNS.** Because the mount happens in the host namespace, an NFS endpoint given as a hostname must resolve through each node's own resolver. An IP address removes this dependency entirely and is the safer choice for a first deployment.

**Node lifecycle is yours to manage.** On OpenShift, MachineConfig keeps node packages consistent as nodes are replaced. On an upstream cluster nothing does that for you, so put the NFS client packages into your node image or configuration management. A node that joins the cluster without them will schedule pods and then fail to mount.

**Version compatibility moves.** The array-side and driver-side floors quoted here — PX-CSI 26.2 for FlashBlade Realms, Purity//FB 4.6.1 for Realms, Purity//FA 6.10.6 and Purity//FB 4.6.0 for NFS over TLS — reflect the PX-CSI 26.2 documentation. Confirm against the current Portworx support matrix before deploying. The client-side floor for NFS over TLS is RHEL 9.6, which is a Red Hat support statement rather than a Portworx one, so the two must be checked separately.

{% include quickstart/nfs-mount-options.md %}

> **Note:** The mount options above describe host-level NFS tuning. In this deployment model they are set through the storage class `mountOptions` field rather than in `/etc/fstab`, and they must stay within what the array export permits.

---

## Next Steps

- Set a cluster default storage class if NFS should be the default for unqualified PVCs.
- Add the NFS client packages to your node image or configuration management so replacement nodes inherit them.
- Create one storage class per service tier rather than per workload, so mount options and export rules stay reviewable.
- Attach quota policies to every FlashArray File Services class that more than one team consumes.
- Decide how RWX file data is protected, given that the `pure_fa_file` backend cannot be snapshotted through the driver.
- Confirm your versions against the Portworx support matrix before adopting NFS over TLS, and check the node OS version separately — TLS needs RHEL 9.6 or later on the client, which is a Red Hat support boundary, not a Portworx one.

---

## Related Articles

- [OpenShift NFS Quickstart](../../openshift/nfs/QUICKSTART.md) — the same two backends on Red Hat OpenShift, with MachineConfig node preparation
- [Installing ktls-utils on Red Hat CoreOS](../../openshift/nfs-tls/QUICKSTART.md) — how the same TLS prerequisite is met on an immutable node, where no package manager is available
- [OpenShift iSCSI Multipathing and NIC Binding via MachineConfig](../../openshift/iscsi/QUICKSTART.md) — block connectivity for Kubernetes nodes on Red Hat CoreOS
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
