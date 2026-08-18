A bonded storage network only helps a single mount if that mount opens more than one TCP connection, so `nconnect` belongs in the storage class `mountOptions` alongside the NFS version.

```yaml
mountOptions:
  - nfsvers=4.1
  - proto=tcp
  - nconnect=4
```

Start at 4 for 10 GbE and 4 to 8 for 25 GbE. The mount option requires a node kernel of 5.3 or later and an NFS version the array export permits; where the export allows only NFSv3, verify on one PVC before rolling the option out broadly. Values above 16 add memory overhead without measurable gain.

> **Important: on PX-CSI 26.2 this behaves differently per backend, and one of them fails silently.**
>
> | Backend | `nconnect` in the live mount |
> |---|---|
> | `pure_file` (FlashBlade) | **Honoured.** Verified with `nconnect=16` on a `vers=4.1` mount |
> | `pure_fa_file` (FlashArray File Services) | **Silently dropped** |
>
> On the FlashArray file backend the option is accepted by the storage class, propagates
> correctly into the PersistentVolume's `spec.mountOptions`, and is then absent from the
> driver's own mount command — while `nfsvers` and `proto` from the same list survive.
> Nothing errors, and the result is one connection where you expected several.
>
> Because the two backends disagree, a storage class that works as intended on FlashBlade
> gives you a single connection on FlashArray File Services. Verify on the backend you are
> actually using rather than carrying the result across.

**Verify on a live mount, two ways.** `/proc/mounts` and `mount` do not reliably display `nconnect` even when it is active, so a missing value there is not proof on its own. Check the effective options and then count the connections:

```bash
# Effective mount options, from the node
nfsstat -m

# The conclusive test: one connection per nconnect slot
ss -tn state established '( dst <nfs-endpoint> )' | wc -l
```

A single established connection to the NFS endpoint means `nconnect` is not in effect,
whatever the mount options claim. The contrast is unmistakable on a working mount: a node
carrying only ordinary mounts to the endpoint held **one** established connection, while a
node with a single `nconnect=16` mount alongside them held **13**.

Count from the node, not from inside the pod, and remember that the count covers every
mount to that endpoint — so compare against a node without the option rather than reading
one number in isolation.

Changing `mountOptions` does not affect volumes already bound. Existing PVCs keep the options they were mounted with until the pod is rescheduled, so treat a change here as taking effect on the next mount rather than immediately.
