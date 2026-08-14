A bonded storage network only helps a single mount if that mount opens more than one TCP connection, so `nconnect` belongs in the storage class `mountOptions` alongside the NFS version. It applies to both backends and to every PVC created from the class.

```yaml
mountOptions:
  - nfsvers=4.1
  - proto=tcp
  - nconnect=4
```

Start at 4 for 10 GbE and 4 to 8 for 25 GbE, and confirm the value survived by checking a live mount from inside a pod with `mount | grep nconnect`. The mount option requires a node kernel of 5.3 or later and an NFS version the array export permits; where the export allows only NFSv3, verify on one PVC before rolling the option out broadly. Values above 16 add memory overhead without measurable gain.

Changing `mountOptions` does not affect volumes already bound. Existing PVCs keep the options they were mounted with until the pod is rescheduled, so treat a change here as taking effect on the next mount rather than immediately.
