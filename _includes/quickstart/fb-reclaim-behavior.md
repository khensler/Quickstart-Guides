**Reclaim on FlashBlade works, but capacity comes back later than the PV does.** Deleting a
PVC removes the PersistentVolume promptly and PX-CSI destroys the backing file system — but
the file system then sits in the array's *destroyed* state until the eradication delay
expires, holding its space the whole time. On a default configuration that is a 24-hour
wait:

```bash
# The file system is gone from the normal listing...
purefs list

# ...but still present, and still consuming capacity, until the timer runs out
purefs list --pending-only
# Name                     Size  Hard Limit  Time Remaining
# px_<...>-pvc-<...>       10G   True        23:59:40
```

This matters when you are churning through test volumes or sizing a pool: capacity is
reclaimed on the array's schedule, not the cluster's. Eradication settings are configured
on the array, so shorten the delay there if a lab needs faster turnaround — and account for
the delay rather than assuming a deleted PVC has freed its space.

> **Note:** This is ordinary, working behaviour and is not the same as the FlashArray File
> Services reclaim problem described in the FlashArray preparation step. There, deletion
> fails outright and the PV never goes away. Here, deletion succeeds and only the space
> lags.
