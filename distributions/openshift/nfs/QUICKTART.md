# Configure Red Hat OpenShift to Use FlashArray File Services

This procedure configures Red Hat OpenShift to dynamically provision ReadWriteMany (RWX) persistent volumes from Pure Storage FlashArray File Services. The supported integration uses Portworx CSI (PX-CSI), a FlashArray file virtual interface, and a Kubernetes `StorageClass` with the `pure_fa_file` backend.

> **Scope:** This article covers dynamic NFS provisioning from FlashArray File Services. It does not cover FlashArray block volumes or manually defined NFS persistent volumes.

For the vendor workflow, see [Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services).

## Prerequisites

Before starting, confirm the following:

* A supported Red Hat OpenShift Container Platform cluster.
* PX-CSI and a compatible Portworx Operator release. These examples align with the PX-CSI 26.2 documentation.
* Administrator access to OpenShift and Storage Admin access to the FlashArray.
* FlashArray File Services is enabled.
* A File VIF/NFS endpoint is configured and reachable from every OpenShift node.
* A FlashArray file system and NFS policy exist.
* A FlashArray Storage Admin API token is available.
* NFS client utilities are available on every OpenShift node that can run a pod using this storage class.
* Routing and firewalls permit NFS traffic between OpenShift nodes and the File VIF.

FlashArray File Services does not require the host multipath or udev configuration used for block volumes.

> **Important:** FlashArray realms do not provide secure multitenancy for FlashArray File Services. Use an account and API token that can manage the required file-service objects.

## Procedure

### 1. Prepare FlashArray File Services

In the FlashArray management interface, verify File Services and configure:

1. A File VIF reachable from the OpenShift nodes.
2. A file system in which PX-CSI can create directories.
3. An NFS policy that allows the OpenShift node networks.
4. Optionally, a quota policy for enforcing directory capacity.

Record the management endpoint, File VIF, file system name, NFS policy name, and optional quota policy name. These objects must exist before PVC provisioning.

Workloads that change ownership or use a pod `fsGroup` can fail when root squashing or NFS user mapping prevents ownership changes. When required by the workload, disable NFS user mapping and configure `no_root_squash` for the authorized OpenShift node network.

> **Security warning:** `no_root_squash` permits root on an authorized client to act as root on the export. Restrict the policy to trusted node addresses and use it only when required.

See [Prepare FlashArray for PX-CSI](https://docs.portworx.com/portworx-csi/install/prepare/flash-array).

### 2. Create the PX-CSI FlashArray configuration

Create `pure.json`:

```json
{
  "FlashArrays": [
    {
      "MgmtEndPoint": "10.20.30.40",
      "APIToken": "REPLACE_WITH_FLASHARRAY_API_TOKEN",
      "NFSEndPoint": "10.20.40.50"
    }
  ]
}
```

Replace the examples with values from the FlashArray. `NFSEndPoint` is required for FlashArray File Services. For IPv6 formatting, see the [PX-CSI pure.json reference](https://docs.portworx.com/portworx-csi/reference/pure-json-reference).

Create the required secret in the PX-CSI namespace:

```bash
export PX_NAMESPACE=portworx

oc create namespace "${PX_NAMESPACE}" --dry-run=client -o yaml | oc apply -f -
oc create secret generic px-pure-secret \
  --namespace "${PX_NAMESPACE}" \
  --from-file=pure.json=./pure.json
oc get secret px-pure-secret --namespace "${PX_NAMESPACE}"
rm -f ./pure.json
```

> **Important:** The secret must be named `px-pure-secret` and be in the namespace where PX-CSI is installed.

### 3. Install or verify PX-CSI

If PX-CSI is not installed, generate an installation specification through [Portworx Central](https://central.portworx.com/). Select Red Hat OpenShift as the distribution and File Storage as the access type. Install the Portworx Operator, then apply the generated `StorageCluster` specification according to [Install PX-CSI](https://docs.portworx.com/portworx-csi/install/install-portworx-csi).

Verify the deployment:

```bash
oc get storagecluster --namespace "${PX_NAMESPACE}"
oc get pods --namespace "${PX_NAMESPACE}" -o wide
oc get csidriver
```

Confirm that the `StorageCluster` is online and the PX-CSI controller and node pods are running.

### 4. Create the FlashArray File StorageClass

Create `fa-file-rwx.yaml`:

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fa-file-rwx
provisioner: pxd.portworx.com
parameters:
  backend: "pure_fa_file"
  pure_nfs_policy: "openshift-nfs"
  pure_fa_file_system: "openshift-files"
  pure_quota_policy: "openshift-100gi"
mountOptions:
  - nfsvers=4.1
  - proto=tcp
reclaimPolicy: Delete
allowVolumeExpansion: true
```

Replace the policy and file system names with existing FlashArray object names. Remove `pure_quota_policy` if no quota policy will be used.

Apply and verify:

```bash
oc apply -f fa-file-rwx.yaml
oc get storageclass fa-file-rwx -o yaml
```

| Parameter | Required | Description |
|---|---:|---|
| `backend: "pure_fa_file"` | Yes | Selects FlashArray File Services. |
| `pure_nfs_policy` | Yes | Names a pre-created FlashArray NFS policy. |
| `pure_fa_file_system` | Yes | Names the pre-created parent file system. |
| `pure_quota_policy` | No | Associates a pre-created quota policy. |
| `pure_nfs_endpoint` | No | Overrides `NFSEndPoint` for this class. |
| `portworx.io/pure-array-id` | No | Targets one array in a multi-array configuration. |

> **Capacity warning:** Without `pure_quota_policy`, the PVC request does not enforce a directory quota. The directory can consume available capacity in the parent file system.

PX-CSI uses NFSv4.1 by default for FlashArray File Services. Use TCP; UDP is not supported. See the [PX-CSI StorageClass reference](https://docs.portworx.com/portworx-csi/reference/storage-class).

### 5. Create and validate an RWX claim

Create `fa-file-test-pvc.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fa-file-test
spec:
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 20Gi
  storageClassName: fa-file-rwx
```

Create `fa-file-test-pod.yaml`:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: fa-file-test
spec:
  securityContext:
    fsGroup: 1000
  containers:
    - name: test
      image: registry.access.redhat.com/ubi9/ubi-minimal:latest
      command: ["/bin/sh", "-c", "echo 'FlashArray File Services test' > /data/test.txt; sleep 3600"]
      volumeMounts:
        - name: data
          mountPath: /data
  volumes:
    - name: data
      persistentVolumeClaim:
        claimName: fa-file-test
```

Apply and verify:

```bash
oc apply -f fa-file-test-pvc.yaml
oc apply -f fa-file-test-pod.yaml
oc wait --for=condition=Ready pod/fa-file-test --timeout=180s
oc get pvc fa-file-test
oc exec fa-file-test -- cat /data/test.txt
oc exec fa-file-test -- mount | grep ' /data '
```

The PVC should be `Bound`, the pod should be `Running`, and the command should return `FlashArray File Services test`. The FlashArray should show a directory and NFS export associated with the persistent volume.

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| PVC remains `Pending` | Missing or misspelled NFS policy/file system; invalid credentials; unhealthy controller | Run `oc describe pvc fa-file-test`, verify `px-pure-secret`, and inspect PX-CSI controller pods and logs. |
| `permission denied` or `lchown failed` | Root squashing or NFS user mapping conflicts with `fsGroup` or ownership changes | Validate the workload UID/GID. When required, disable user mapping and use a node-restricted `no_root_squash` policy. |
| Mount timeout or no route to host | File VIF, routing, firewall, DNS, or NFS client issue | Identify the scheduled node with `oc get pod -o wide`; validate connectivity from that node network to `NFSEndPoint`. |
| Requested size is not enforced | No quota policy is assigned | Create a FlashArray quota policy and reference it through `pure_quota_policy`. |
| PV remains `Released` or deletion fails | The FlashArray file directory is not empty | Preserve required data, remove files before deleting the PVC, and retry cleanup. See [Delete a PersistentVolumeClaim](https://docs.portworx.com/portworx-csi/manage-provisioned-storage/delete-pvc). |

## Optional: NFS over TLS

PX-CSI 26.2 documentation supports NFS over TLS with Purity//FA 6.10.6 or later, Linux kernel 6.12 or later on worker nodes, and the required NFS/TLS packages. After validating all prerequisites, add:

```yaml
mountOptions:
  - nfsvers=4.1
  - proto=tcp
  - xprtsec=tls
```

See [Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services) and the [PX-CSI release notes](https://docs.portworx.com/portworx-csi/release-notes).

## Cleanup

Remove test data before deleting the resources:

```bash
oc exec fa-file-test -- rm -f /data/test.txt
oc delete pod fa-file-test
oc delete pvc fa-file-test
oc get pv
```

Do not delete the storage class, PX-CSI deployment, or `px-pure-secret` if other workloads use them.

## References

1. [Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array) — File Services prerequisites, credentials, NFS policy guidance, `pure.json`, and the secret.
2. [Portworx CSI — Install PX-CSI](https://docs.portworx.com/portworx-csi/install/install-portworx-csi) — Operator and PX-CSI installation on OpenShift.
3. [Portworx CSI — Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services) — Backend, StorageClass, PVC workflow, mount options, and limitations.
4. [Portworx CSI — StorageClass Reference](https://docs.portworx.com/portworx-csi/reference/storage-class) — StorageClass parameters.
5. [Portworx CSI — FlashArray and FlashBlade JSON File Reference](https://docs.portworx.com/portworx-csi/reference/pure-json-reference) — Endpoint and credential fields.
6. [Portworx CSI — System Requirements](https://docs.portworx.com/portworx-csi/system-requirements) — Node, network, package, and platform requirements.
7. [Portworx CSI — Delete a PersistentVolumeClaim](https://docs.portworx.com/portworx-csi/manage-provisioned-storage/delete-pvc) — FlashArray File cleanup behavior.
8. [Portworx CSI — Release Notes](https://docs.portworx.com/portworx-csi/release-notes) — Release-specific compatibility information.
