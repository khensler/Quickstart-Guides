### What Target-Driven Rescan Does

Target-Driven Rescan (TDR) is a FlashArray host-integration capability: the array signals the host when volumes are connected or disconnected, so the host updates its device state without an administrator running a manual rescan for normal operations. Some operating systems, Windows among them, handle TDR fully with no host-side configuration.

On Linux, automatic discovery of *additional* volumes has worked for some time through target-driven SCSI notifications. Full cleanup of *disconnected* devices is newer and depends on `multipath-tools` v0.14.0 together with the `purge_disconnected` multipath setting.

This distinction matters operationally. Disconnecting a volume without purging stale devices can leave disconnected paths or devices behind on the host — a real risk if a different volume is later connected using the same LUN number.

### What It Replaces

Historically an administrator had to log in to each Linux host and run rescan or cleanup commands after every ACL change on the array. TDR moves that work to the target: the array raises standard protocol events and the host reacts on its own.

With the Linux pieces in place, the workflow becomes: connect a volume on the array and wait for it to appear; disconnect it and wait for it to disappear. No manual rescan and no manual device removal on the initiator.

### Releases That Support `purge_disconnected`

| Distribution | Version |
|---|---|
| Red Hat Enterprise Linux | 9.8 |
| Red Hat Enterprise Linux | 10.2 |
| SUSE Linux | 16.1 |
| Ubuntu Linux | 26.04 |
| Debian Linux | 14 |

These are the releases Everpure documents for automatic disconnected-device cleanup. For a distribution not listed — including RHEL rebuilds such as Oracle Linux — confirm the installed `multipath-tools` is v0.14.0 or newer before relying on automatic purge.

### How Volume Discovery Works

When a volume is mapped to a host that **already has at least one connected volume**, the array returns Unit Attention sense data `3Fh/0Eh` (REPORTED LUNS DATA HAS CHANGED) down the established paths. The host reads that as a signal to rescan visible LUNs on those paths and picks up the new volume automatically.

Discovery of the **first** volume depends on the transport, and the two behave differently:

- **Fibre Channel** — hosts are normally already logged in to reachable target ports before any volume is connected. To force discovery of the first LUN, the array logs the host ports out of those target ports. The host immediately logs back in, repeats SCSI discovery, and finds the new volume.
- **iSCSI** — first-volume discovery works only if the host is already logged in to the array when the volume is connected. Linux permits a host to log in with no volumes connected, provided the host object already exists on the array. Once those sessions are established, connecting the first volume lets the array signal the host to rescan.

### How Volume Removal Works

On disconnect the host has to do more than notice a failed path — it has to purge the stale device so its view matches what the array still presents.

- If the disconnected volume is **not** the last one connected to the host, the array again uses `3Fh/0Eh` to trigger a rescan, after which the host no longer finds the disconnected LUN.
- If the volume is no longer present on a path, the array can return `25h/00h` (LOGICAL UNIT NOT SUPPORTED). Once every path to that volume returns this, the host can remove the volume from its configuration. The same mechanism removes a single stale path while leaving the volume online when other working paths remain.

### Enabling Disconnect Cleanup

Automatic purge requires `purge_disconnected "yes"` on the FlashArray device entry in `/etc/multipath.conf`. Add the single key to the `PURE`/`FlashArray` device stanza already defined in the multipath section of this guide:

```
devices {
    device {
        vendor  "PURE"
        product "FlashArray"
        # ... keep the settings already given in the Multipath Configuration section
        purge_disconnected "yes"    # required for automatic disconnected-device cleanup
    }
}
```

> **Note:** Everpure's TDR reference article shows a full device stanza alongside this setting, and some of its values differ from the ones this guide recommends — notably `no_path_retry "fail"` and `dev_loss_tmo 600`. Do not merge the two blocks. Keep the device stanza from the Multipath Configuration section of this guide, which is tuned for this distribution and protocol, and add only `purge_disconnected "yes"` to it.

> **Warning:** If you are using ActiveCluster, do not enable `purge_disconnected` unless the array is running Purity//FA 6.9.6 or later.

### What to Expect

When an added volume is discovered, new SCSI devices appear and the volume shows up under multipath with no manual rescan command.

When a disconnected volume is purged successfully, the system log shows the paths going disconnected, ALUA detach messages for the SCSI devices, and multipath flushing the map once all paths are gone.

### When Manual Intervention Is Still Needed

Everything above assumes the host has the multipath behavior required for stale-device purge. Without it, a disconnect is still *detected*, but the device is likely to sit in a failed state rather than being removed — at which point manual cleanup is required.

### Operational Checklist

For hosts that should use TDR for both add and remove workflows:

- Confirm `multipath-tools` v0.14.0 or newer, for disconnected-device purging.
- Set `purge_disconnected "yes"` on the `PURE`/`FlashArray` device entry.
- On ActiveCluster, require Purity//FA 6.9.6 or later before enabling it.
- Meet the normal connectivity prerequisites for the transport: zoning plus a host definition for Fibre Channel, established sessions plus a host definition for iSCSI.
- After connecting or disconnecting a volume, give the host and multipath stack time to process the target-driven event instead of immediately running a manual rescan.
