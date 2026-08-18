> **Important: confirm that volumes can be *deleted* before you adopt this backend.**
> Provisioning working is not evidence that reclaim works. PX-CSI deletes a
> `pure_fa_file` volume by restoring the managed directory to the `.px.base` snapshot
> it took when the volume was created, and that restore needs the array's
> **managed directory overwrite** capability. Where the capability is off, volumes
> provision and mount perfectly but can never be reclaimed — every PVC permanently
> leaks a managed directory and its export on the array.

Prove it on one throwaway volume, before any real workload depends on the backend:

```bash
kubectl apply -f test-pvc.yaml     # wait for Bound
kubectl delete pvc <test-pvc>
kubectl get pv | grep <pvc-name>   # expect the PV to disappear, not sit at Released
```

If the PV stays `Released`, check the controller log. Only the **leader** of the
controller-plugin replicas logs the failure — the others show nothing, which makes this
easy to misdiagnose if you happen to check the wrong pod:

```bash
kubectl -n portworx logs -l app.kubernetes.io/component=controller-plugin \
  -c controller-plugin --tail=200 | grep -i "restore directory"
# Failed to delete backend volume ... failed to restore directory from snapshot (400):
# Msg1: Managed directory overwrite is not supported since feature flag is disabled
```

Selecting on the label rather than naming a pod matters here: it covers all replicas, so
you see the leader's message without having to work out which replica is the leader.

That message is definitive: it is an array-side capability, not a Kubernetes,
StorageClass, or permissions problem. There is no admin-accessible switch for it —
Purity exposes no CLI command for managed directory overwrite (`puredir copy` is
documented as unable to overwrite an existing managed directory), so **enabling it
requires Everpure Support**. Open a case asking for managed directory overwrite to be
enabled on the array, and re-run the test above before proceeding.

> **Note:** Do not confuse this with a directory that still holds data. A managed
> directory containing files is a *separate* cause of deletion failure, and emptying the
> directory does nothing for the capability failure above — the restore is refused before
> content is ever considered. The controller log is what tells the two apart.

**Cleaning up volumes that already leaked.** The directories cannot be removed
individually while their `.px.base` client snapshots exist, so reclaim them at the parent
file system. Order matters, and the file system refuses to be destroyed until every export
on its directories is gone:

```bash
# 1. On the cluster: remove the pods, then the PVCs, then the PVs. Deleting a PVC leaves
#    the PV stuck in Released with a finalizer, because the backend delete keeps failing.
kubectl delete pod  <pods using the volumes>
kubectl delete pvc  <pvcs>
kubectl delete pv   <pvs>                    # will not complete on its own
kubectl patch pv <pv> --type=merge -p '{"metadata":{"finalizers":null}}'

# 2. On the array: confirm the file system holds only the leaked PX directories.
purefs list
puredir list --file-system <file-system>

# 3. Remove every export on those directories FIRST. Destroying the file system while any
#    remain fails with "Managed directory is connected to an active export policy."
puredir export list --dir <directory>
puredir export delete <export-name>

# 4. Then the file system, which takes its directories and their snapshots with it.
purefs destroy <file-system>
purefs eradicate <file-system>
```

> **Note:** Delete the *exports*, not the export *policies*. A policy is a reusable array
> object that other directories — and other teams — may depend on. Removing an export
> detaches only that one directory from the policy.

Leave the NFS and quota policies in place if you intend to re-provision; they are
referenced by the storage class, not by the deleted volumes.
