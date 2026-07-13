# Quickstart: Red Hat OpenShift with FlashArray File Services
This quickstart configures Red Hat OpenShift Container Platform to dynamically provision ReadWriteMany (RWX) persistent volumes from Pure Storage FlashArray File Services. The supported integration uses Portworx CSI (PX-CSI), a FlashArray file virtual interface, and a Kubernetes `StorageClass` with the `pure_fa_file` backend.
> **Scope:** This article covers dynamic NFS provisioning from FlashArray File Services. It does not cover FlashArray block volumes or manually defined NFS persistent volumes.
For the Portworx documentation, see [Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services).
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
## Workflow Overview

The deployment has five phases:

1. Prepare FlashArray File Services, its File VIF, parent file system, NFS policy, and optional quota policy.
2. Create the FlashArray API token and the `px-pure-secret` configuration.
3. Install or validate PX-CSI on OpenShift.
4. Create a FlashArray File `StorageClass`.
5. Provision and validate an RWX persistent volume.

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
Create a `pure.json` file describing the FlashArray management endpoint, API token, and NFS endpoint. `NFSEndPoint` is required for FlashArray File Services. For the field list and IPv6 formatting, see the [PX-CSI pure.json reference](https://docs.portworx.com/portworx-csi/reference/pure-json-reference).

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
Create a `StorageClass` (for example, `fa-file-rwx.yaml`) with `provisioner: pxd.portworx.com` and `backend: "pure_fa_file"`, referencing your pre-created FlashArray objects through `pure_nfs_policy` and `pure_fa_file_system`. Optionally set `pure_quota_policy` to enforce a directory size limit and `allowVolumeExpansion: true`. For the full parameter list, the NFSv4.1/TCP defaults, and the multiserver limitation, see [Create a StorageClass](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services#create-a-storageclass) and the [PX-CSI StorageClass reference](https://docs.portworx.com/portworx-csi/reference/storage-class).

Apply and verify:

```bash
oc apply -f fa-file-rwx.yaml
oc get storageclass fa-file-rwx -o yaml
```

> **Capacity warning:** Without `pure_quota_policy`, the PVC request does not enforce a directory quota. The directory can consume available capacity in the parent file system.

### 5. Create and validate an RWX claim

Create a `ReadWriteMany` PVC (`fa-file-test-pvc.yaml`) that sets `storageClassName: fa-file-rwx`, and a test pod (`fa-file-test-pod.yaml`) that mounts it at `/data` and writes a file such as `/data/test.txt`. On OpenShift, set a pod `securityContext.fsGroup` so the workload can write to the mount. For the full PVC and pod field reference, including `nodeAffinity`/topology options, see [Create a PVC](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services#create-a-pvc) and [Mount a PVC to a Pod](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services#mount-a-pvc-to-a-pod).

Apply and verify:
```bash
oc apply -f fa-file-test-pvc.yaml
oc apply -f fa-file-test-pod.yaml
oc wait --for=condition=Ready pod/fa-file-test --timeout=180s
oc get pvc fa-file-test
oc exec fa-file-test -- cat /data/test.txt
oc exec fa-file-test -- mount | grep ' /data '
```
The PVC should be `Bound`, the pod should be `Running`, and the `cat` command should return the contents you wrote to `/data/test.txt`. The FlashArray should show a directory and NFS export associated with the persistent volume.
## Troubleshooting
| Symptom | Likely cause | Resolution |
|-|-|-|
| PVC remains `Pending` | Missing or misspelled NFS policy/file system; invalid credentials; unhealthy controller | Run `oc describe pvc fa-file-test`, verify `px-pure-secret`, and inspect PX-CSI controller pods and logs. |
| `permission denied` or `lchown failed` | Root squashing or NFS user mapping conflicts with `fsGroup` or ownership changes | Validate the workload UID/GID. When required, disable user mapping and use a node-restricted `no_root_squash` policy. |
| Mount timeout or no route to host | File VIF, routing, firewall, DNS, or NFS client issue | Identify the scheduled node with `oc get pod -o wide`; validate connectivity from that node network to `NFSEndPoint`. |
| Requested size is not enforced | No quota policy is assigned | Create a FlashArray quota policy and reference it through `pure_quota_policy`. |
| PV remains `Released` or deletion fails | The FlashArray file directory is not empty | Preserve required data, remove files before deleting the PVC, and retry cleanup. See [Delete a PersistentVolumeClaim](https://docs.portworx.com/portworx-csi/manage-provisioned-storage/delete-pvc). |

## Optional: NFS over TLS

PX-CSI supports NFS over TLS by adding `xprtsec=tls` to the storage class `mountOptions`. This requires a minimum Purity//FA version, a supported worker-node kernel, and the `nfs-utils`, `ktls-util` (`tlshd`), and `openssl` packages on each node. For the exact version and package requirements, see [Create a StorageClass](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services#create-a-storageclass) and the [PX-CSI release notes](https://docs.portworx.com/portworx-csi/release-notes).

## Cleanup

Remove test data before deleting the resources:
```bash
oc exec fa-file-test -- rm -f /data/test.txt
oc delete pod fa-file-test
oc delete pvc fa-file-test
oc get pv
```
Do not delete the storage class, PX-CSI deployment, or `px-pure-secret` if other workloads use them.

## Appendix: Consolidated Command Reference

```bash
export PX_NAMESPACE=portworx

oc create namespace "${PX_NAMESPACE}" --dry-run=client -o yaml | oc apply -f -
oc create secret generic px-pure-secret --namespace "${PX_NAMESPACE}" --from-file=pure.json=./pure.json
oc get secret px-pure-secret --namespace "${PX_NAMESPACE}"

oc get storagecluster --namespace "${PX_NAMESPACE}"
oc get pods --namespace "${PX_NAMESPACE}" -o wide
oc get csidriver

oc apply -f fa-file-rwx.yaml
oc get storageclass fa-file-rwx -o yaml

oc apply -f fa-file-test-pvc.yaml
oc apply -f fa-file-test-pod.yaml
oc wait --for=condition=Ready pod/fa-file-test --timeout=180s
oc get pvc fa-file-test
oc get pod fa-file-test -o wide
oc exec fa-file-test -- cat /data/test.txt
oc exec fa-file-test -- mount | grep ' /data '

oc exec fa-file-test -- rm -f /data/test.txt
oc delete pod fa-file-test
oc delete pvc fa-file-test
oc get pv
```

## References
[Portworx CSI — Prepare FlashArray](https://docs.portworx.com/portworx-csi/install/prepare/flash-array) — File Services prerequisites, credentials, NFS policy guidance, `pure.json`, and the secret.
[Portworx CSI — Install PX-CSI](https://docs.portworx.com/portworx-csi/install/install-portworx-csi) — Operator and PX-CSI installation on OpenShift.
[Portworx CSI — Dynamic Provisioning of FlashArray File Services](https://docs.portworx.com/portworx-csi/provision-storage/dynamic-provisioning/flasharray-file-services) — Backend, StorageClass, PVC workflow, mount options, and limitations.
[Portworx CSI — StorageClass Reference](https://docs.portworx.com/portworx-csi/reference/storage-class) — StorageClass parameters.
[Portworx CSI — FlashArray and FlashBlade JSON File Reference](https://docs.portworx.com/portworx-csi/reference/pure-json-reference) — Endpoint and credential fields.
[Portworx CSI — System Requirements](https://docs.portworx.com/portworx-csi/system-requirements) — Node, network, package, and platform requirements.
[Portworx CSI — Delete a PersistentVolumeClaim](https://docs.portworx.com/portworx-csi/manage-provisioned-storage/delete-pvc) — FlashArray File cleanup behavior.
[Portworx CSI — Release Notes](https://docs.portworx.com/portworx-csi/release-notes) — Release-specific compatibility information.
