### FlashArray File Services volumes may provision successfully but fail to delete

**Applies to:** PX-CSI with the `pure_fa_file` backend (FlashArray File Services).
FlashBlade `pure_file` volumes are not affected and reclaim normally.

**Symptom.** PVCs bind, mount, and serve I/O correctly, including `ReadWriteMany` across
nodes. Deleting the PVC then leaves the PersistentVolume in `Released` indefinitely, and the
managed directory and its export remain on the array. Because provisioning and mounting are
unaffected, a functional test can pass completely and the problem appears only at cleanup.

**Cause.** PX-CSI deletes a `pure_fa_file` volume by restoring the volume's managed directory
to the base snapshot taken when the volume was created. That restore requires the array's
**managed directory overwrite** capability. Where the capability is not enabled, the array
refuses the operation and the driver cannot complete the delete. Purity exposes no
administrator command for it, so it cannot be enabled from the array's CLI.

**How to confirm it.** Check the controller log. Only the current leader among the
controller-plugin replicas records the failure, so select on the label rather than naming a
single pod:

```bash
kubectl -n portworx logs -l app.kubernetes.io/component=controller-plugin \
  -c controller-plugin --tail=200 | grep -i "restore directory"
# ... failed to restore directory from snapshot (400):
#     Msg1: Managed directory overwrite is not supported since feature flag is disabled
```

That message is definitive and identifies this issue specifically. It is an array capability
result, not a Kubernetes, StorageClass, or permissions problem.

> **Important:** Do not confuse this with a managed directory that still contains data, which
> is a separate and legitimate cause of deletion failure. Emptying the directory does not
> resolve this issue — the restore is refused before directory contents are considered. The
> controller log is what distinguishes the two.

**Resolution.** Contact Everpure Support and ask for managed directory overwrite to be
enabled on the array. Then confirm the fix by provisioning one disposable PVC, deleting it,
and verifying the PersistentVolume disappears rather than settling at `Released`.

**Recommended precaution.** Run that same delete test on a disposable volume *before*
adopting this backend for any workload. Provisioning working is not evidence that reclaim
works, and until reclaim is confirmed, every PVC leaves a managed directory and an export
behind on the array.

**Reclaiming volumes that already leaked.** Directories cannot be removed individually while
their base snapshots exist, so reclaim them through the parent file system, after confirming
it holds nothing else you need. Remove every export on the affected directories first — the
file system refuses to be destroyed while any export remains, reporting
`Managed directory is connected to an active export policy`. Delete the exports, not the
export policies, which are reusable objects other directories may depend on.
