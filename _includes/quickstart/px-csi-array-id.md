A `pure.json` holding more than one FlashArray is ambiguous to the provisioner unless you
say which array a class should use. Without that, provisioning fails outright:

```
CreateVolume failed: flasharray backend provisioning failed:
multiple storage backends match volume provisioner,
unable to determine which backend the provided NFSEndpoint matches to
```

Pin the class with `portworx.io/pure-array-id`, using the array's ID from
`purearray list`:

```yaml
parameters:
  backend: "pure_fa_file"
  portworx.io/pure-array-id: "<array-id>"    # e.g. 732c61c2-d22f-4f92-a7e7-49433985267f
  pure_nfs_policy: "<nfs-policy>"
  pure_fa_file_system: "<fa-file-system>"
```

Three things about this parameter are easy to get wrong:

- **It is namespaced.** `portworx.io/pure-array-id`, not the `pure_`-prefixed style of
  every backend parameter beside it in the same class.
- **`pure_nfs_endpoint` does not do this job.** Naming the File VIF identifies an
  endpoint, not a backend, and a class that sets it can still fail to select an array.
- **It applies to every backend**, not only file. A PVC annotation of the same name
  overrides the class.

> **Warning:** Adding an array to `pure.json` affects **all** backends on the cluster,
> not just the one you are configuring. On a cluster already serving `pure_block`, adding
> a file-serving array can stop block provisioning working:
>
> ```
> CreateVolume failed: flasharray backend provisioning failed:
>   not able to discover any PureBackend for Volume
>   no IQN or iSCSI portals found for iSCSI transport
> ```
>
> Volumes already bound keep working, so nothing looks wrong until the next new volume is
> requested — possibly long afterwards, with no obvious link back to the change.

**Fixing the classes you already have.** You usually cannot. A StorageClass's
`parameters` are immutable:

```
The StorageClass "px-fa-direct-access" is invalid:
parameters: Forbidden: updates to parameters are forbidden.
```

and the driver's default classes are operator-owned
(`operator.libopenstorage.org/managed-by: portworx`), so deleting and recreating one
gets it restored without your parameter. Use the **PVC annotation** instead, which
overrides the class and needs no change to it:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-block-volume
  annotations:
    portworx.io/pure-array-id: "<block-array-id>"
spec:
  storageClassName: px-fa-direct-access
  ...
```

For classes you own, set the parameter at creation time; for the driver's defaults and
anything already in use, annotate the claim. Where neither is practical — an existing
workload you cannot re-annotate — create a new class pinned at creation and migrate to
it.

**Test both backends after any `pure.json` change.** Provision one throwaway volume per
backend and confirm each binds. This is the only way to catch the breakage while you
still remember what you changed.
