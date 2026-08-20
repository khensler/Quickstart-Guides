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

> **`no_path_retry 0` does not mean "fail immediately".** It absorbs roughly the
> first 20 seconds of an all-paths-down window before the application sees `EIO`,
> because the transport has not yet declared the paths dead. A normal
> single-controller failover completes well inside that window. Choose `0` when
> you want the layer above the device to see an error and act on it — not because
> you expect instant failure.

> **`polling_interval` scales every value in the table.** This guide sets
> `polling_interval 10`; the multipath built-in default is `5`, which halves the
> tolerance for every `no_path_retry` above 0. If you change one, restate the
> other.

**Recovery is slower than failure.** Once connectivity returns, multipathd has to
notice — and it widens its check interval toward `max_polling_interval` while
paths are healthy, so it is slow to spot their return. Expect I/O to resume
**tens of seconds after** the paths are actually back, not immediately. The
outage your application experiences is the outage duration *plus* that recovery
tail.

**Avoid tuning to the edge.** Setting `no_path_retry` so its tolerance lands close
to your expected failover duration is the worst case: paths get failed at the
moment connectivity returns, so you take both the I/O errors *and* a slower
recovery while the map is rebuilt. Leave headroom rather than aiming for
precision.

#### Verify the effective value, never the config file

A `defaults {}` value is not what you get. Device stanzas override `defaults {}`,
and files in `/etc/multipath/conf.d/` are layered *after* `/etc/multipath.conf`,
so the last definition wins. Read the effective value from the running daemon:

```bash
# The 'queueing' column is the effective no_path_retry for each map
sudo multipathd show maps status

# The fully resolved configuration, including built-in defaults
sudo multipath -t
```

`queueing off` means fail (`no_path_retry 0`), a number means that many retries
remain, and `on` means unbounded queueing.
