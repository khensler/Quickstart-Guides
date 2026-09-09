### How long an outage the host survives

`no_path_retry` is only half the story, and it is not the half that governs a
short outage. Before dm-multipath is consulted at all, the iSCSI transport has to
notice the paths are gone. That takes a fixed amount of time, and it sets a floor
underneath every `no_path_retry` value:

```
tolerance  =  (noop_out_interval + noop_out_timeout + recovery_tmo)  +  (no_path_retry × polling_interval)
              \_________________ transport detection _____________/     \______ dm-multipath queueing ______/
```

- **`noop_out_interval` + `noop_out_timeout`** — a NOP-Out is sent this long after
  the last successful receive, then this long again waiting for the reply. With
  the common default of `5` + `5`, detection takes up to **10 s** (5–10 s
  depending on whether the host was idle when the outage began).
- **`recovery_tmo`** — how long session recovery runs before the device is
  offlined and paths can be failed. **multipathd overwrites this with
  `fast_io_fail_tmo`**, so our `fast_io_fail_tmo 10` makes it 10 s.
- **`no_path_retry × polling_interval`** — only after *all* paths are failed does
  dm-multipath begin its retry countdown, `no_path_retry` checks at
  `polling_interval` seconds apart.

With the settings in this guide (`noop_out_* 5/5`, `fast_io_fail_tmo 10`,
`polling_interval 10`) that works out to:

| `no_path_retry` | Outage the host rides out without an I/O error |
| --- | --- |
| `0` / `fail` | **~20 s** |
| `3` | ~50 s |
| `5` | ~70 s |
| `10` | ~120 s |
| `queue` | unbounded — I/O queues until paths return |

#### The measurements behind the table

These are not calculated figures. They were measured on one stack, and the
detection term depends on values that differ between distributions and
`multipath-tools` releases — so treat the **formula** as portable and the
**constant** as something to re-measure on your own hosts.

*Tested configuration:* Proxmox VE 9.2.2, kernel 7.0.2-6-pve, multipath-tools
0.11.1-2, against Purity//FA 6.12.0 over iSCSI with 8 paths (4 per controller).
Raw block device, `O_DIRECT` 4 KiB writes every 100 ms. All paths dropped by
blackholing both directions to every target portal. 18 runs.

| `no_path_retry` | Predicted | First `EIO` measured |
| --- | --- | --- |
| `0` / `fail` | 20.5 s | 20.5 – 20.8 s |
| `3` | 50.5 s | 50.7 – 51.2 s |
| `5` | 70.5 s | 70.6 – 71.0 s |
| `10` | 120.5 s | 120.7 – 121.0 s |
| `queue` | unbounded | no error in 300 s |

The ~20.5 s floor breaks down as two transport timers in series, taken from the
kernel's own counters rather than inferred:

| Phase | Measured | Set by |
| --- | --- | --- |
| Connection failure detection | 10.07 – 10.11 s | `noop_out_interval` 5 + `noop_out_timeout` 5 |
| Session recovery window | 10.24 s | `recovery_tmo` 10 (forced from `fast_io_fail_tmo`) |
| **Total to first `EIO`** | **≈ 20.4 s** | |

Every one of the 18 runs recovered to 8/8 paths with no manual intervention.

> **`no_path_retry 0` does not mean "fail immediately".** It absorbs roughly the
> first 20 seconds of an all-paths-down window before the application sees `EIO`,
> because the transport has not yet declared the paths dead. In testing it rode
> out a 15 s outage with zero errors — one write blocked for 16.1 s and then
> succeeded. A normal single-controller failover completes well inside that
> window. Choose `0` when you want the layer above the device to see an error and
> act on it — not because you expect instant failure.

> **`polling_interval` scales every value in the table.** This guide sets
> `polling_interval 10`; the multipath built-in default is `5`, which halves the
> tolerance for every `no_path_retry` above 0. If you change one, restate the
> other. Note also that `polling_interval` plays **no part in detection** — the
> transport fails the path, not multipathd's path checker.

**Recovery is slower than failure.** Once connectivity returns, multipathd has to
notice — and it widens its check interval toward `max_polling_interval` while
paths are healthy, so it is slow to spot their return. Measured recovery ran
**12.6 – 36.2 s** after paths were restored, with full 8/8 restoration taking up
to ~34 s. The outage your application experiences is the outage duration *plus*
that recovery tail.

**Avoid tuning to the edge.** Setting `no_path_retry` so its tolerance lands close
to your expected failover duration is the worst case, and it measured worse than a
longer outage. `no_path_retry 0` against a 20 s outage — right at the ~20.5 s
threshold — produced **228 errors and a 23.2 s recovery**, against 220 errors and
12.6 s for a 30 s outage. Paths were failed at the moment connectivity returned,
so the map was torn down and then had to be rebuilt. Leave headroom rather than
aiming for precision.

#### Two timers that do not behave the way they look

**`node.session.timeo.replacement_timeout` has no effect on a multipathed
volume.** multipathd overwrites the session `recovery_tmo` with
`fast_io_fail_tmo` on every device it manages, so whatever you set here is
discarded. It *is* live on a **non-multipathed** iSCSI device, where it gives
roughly `10 + replacement_timeout` seconds of tolerance — about 130 s at the
common default of 120.

That asymmetry makes it a trap: the same `iscsid.conf` yields ~20 s on a
multipathed volume and ~130 s on a single-path one. Validate this setting on a
single-path test device and you will conclude it works, then see no effect in
production. The knobs that actually move the floor are `fast_io_fail_tmo` /
`recovery_tmo` and the `noop_out_*` pair.

**The 30 s SCSI command timeout becomes the binding constraint if you lengthen
the iSCSI timers.** `/sys/block/sdX/device/timeout` defaults to 30 s. The
transport chain above completes at ~20.4 s, so the command timeout never fires
first — about 10 s of headroom. Raise `fast_io_fail_tmo` much past **~20**, or
lengthen the `noop_out_*` timers, and the SCSI command timeout fires first
instead. That does not just shift the number; it changes the failure mode from
"the transport offlines the device" to "the SCSI command times out", with
different kernel messages and different recovery behaviour. If you lengthen these
timers, raise `/sys/block/sdX/device/timeout` to match, or accept the change of
failure mode deliberately.

#### Verify the effective value, never the config file

A `defaults {}` value is not what you get. Device stanzas override `defaults {}`,
and files in `/etc/multipath/conf.d/` are layered *after* `/etc/multipath.conf`,
so the last definition wins. In testing, a host with `no_path_retry queue` in
`defaults{}` reported `queueing off` on every map, overridden by a `conf.d`
device stanza. Read the effective value from the running daemon:

```bash
# The 'queueing' column is the effective no_path_retry for each map
sudo multipathd show maps status

# The fully resolved configuration, including built-in defaults
sudo multipath -t
```

`queueing off` means fail (`no_path_retry 0`), a number means that many retries
remain, and `on` means unbounded queueing.

Note also that `no_path_retry` **overrides** `features "1 queue_if_no_path"` when
both are set in the same stanza — the `features` entry is silently discarded.
