Two separate things are needed: connections that come back **at boot**, and
connections that come back **after a path failure**. `nvmf-autoconnect.service` only
does the first — it is a one-shot that runs at boot, not a reconnect daemon.

**1. Reconnect at boot**

```bash
# Discovery configuration - list EVERY array this host uses.
# --persistent --ctrl-loss-tmo=-1 keeps a discovery controller alive per portal,
# which is what makes the path-failure recovery in step 2 work after a reboot.
sudo tee /etc/nvme/discovery.conf > /dev/null <<EOF
-t tcp -a <PORTAL_IP_1> -s 4420 --host-traddr <HOST_IP_1> --persistent --ctrl-loss-tmo=-1
-t tcp -a <PORTAL_IP_2> -s 4420 --host-traddr <HOST_IP_1> --persistent --ctrl-loss-tmo=-1
-t tcp -a <PORTAL_IP_3> -s 4420 --host-traddr <HOST_IP_2> --persistent --ctrl-loss-tmo=-1
-t tcp -a <PORTAL_IP_4> -s 4420 --host-traddr <HOST_IP_2> --persistent --ctrl-loss-tmo=-1
EOF

sudo systemctl enable --now nvmf-autoconnect.service
```

`--persistent` and `--ctrl-loss-tmo` are honoured per portal here, so the discovery
controllers that step 2 depends on are re-established at every boot rather than
only for the current uptime.

> **Check your version first — this file changed.** Run `nvme --version`.
> `discovery.conf` is correct for **2.x**, which is what current distributions
> ship (verified on 2.13). It was **retired in nvme-cli 3.0**, which uses
> `/etc/nvme/nvme-fabrics.conf` instead — see below.

**1b. Reconnect at boot — nvme-cli 3.0 and later**

On 3.0 the same configuration lives in `/etc/nvme/nvme-fabrics.conf`, in INI
format. The reliable way to get there is to convert a working 2.x file rather than
hand-write it:

```bash
# Convert an existing discovery.conf, then check what it produced
sudo nvme config convert
sudo nvme config-show
```

Convert **deliberately**. If you do not, the first fabrics command converts it for
you — you do not want that happening for the first time during an incident.

Hand-authored, the equivalent of the 2.x file above is:

```ini
[Discovery Controller Defaults]
ctrl-loss-tmo = -1

[Discovery Controller]
controller = transport=tcp;traddr=<PORTAL_IP_1>;trsvcid=4420;host-traddr=<HOST_IP_1>
controller = transport=tcp;traddr=<PORTAL_IP_2>;trsvcid=4420;host-traddr=<HOST_IP_1>
controller = transport=tcp;traddr=<PORTAL_IP_3>;trsvcid=4420;host-traddr=<HOST_IP_2>
controller = transport=tcp;traddr=<PORTAL_IP_4>;trsvcid=4420;host-traddr=<HOST_IP_2>
```

One `controller` line per path, each pinned to the host address that should carry
it — the direct equivalent of `--host-traddr` in the 2.x file. To pin by interface
name instead of host address, use `host-iface=<NIC>`:

```ini
controller = transport=tcp;traddr=<PORTAL_IP_1>;trsvcid=4420;host-iface=<NIC_A>
```

Three things to know when you migrate:

- **You no longer need to ask for persistence.** From 3.0 discovery controllers are
  persistent by default, which is the behaviour step 2 relies on — so the
  `--persistent` flag required in the 2.x file has no counterpart to set here.
- **The keys inside a `controller` value are the `nvme connect` option names**,
  hyphenated — so `host-traddr`, `host-iface`, `ctrl-loss-tmo`, `keep-alive-tmo`,
  `reconnect-delay`. Any of them may appear on a `controller` line as a per-path
  override, which is how you give one fabric different timers from the other.
- **Security parameters are the exception** — they are not overridable per path
  and stay at the section level.

The same `controller` syntax applies in a `[Subsystem]` section, so I/O
connections are pinned the same way.

> **Verify pinning before the host goes into service.** On a dual-fabric host,
> connections that are not pinned will appear to work while quietly using one
> fabric for everything — you find out during a fabric failure, not before.
>
> ```bash
> sudo nvme config-show     # confirm each controller line carries its host-traddr
> sudo nvme list-subsys     # confirm each path is established over the intended NIC
> ```

> **Confirm the discovery controllers came back after a reboot**, not just after
> running the command:
>
> ```bash
> sudo nvme list-subsys | grep -c discovery    # must be non-zero
> ```
>
> If this returns `0` after a reboot, run the `nvme discover` loop from step 2 out
> of a `systemd` unit ordered before your storage consumers instead.

**2. Reconnect after a path failure (persistent discovery controllers)**

If `ctrl_loss_tmo` expires, the kernel does not merely fail I/O — it removes the
controllers, the namespace and the subsystem. Nothing on a stock host brings them
back, so a transient outage becomes an outage that persists after the fault clears.

The recovery mechanism is already installed and enabled
(`70-nvmf-autoconnect.rules` → `nvmf-connect@.service`), but it fires only on a
discovery-log-change event, which requires a **live discovery controller**. Create
one per portal, per host interface:

```bash
# --ctrl-loss-tmo=-1 on the DISCOVERY controller is essential: it has to survive
# the same outage that removed the I/O controllers, or there is nothing left to
# raise the event that triggers reconnection.
for portal in <PORTAL_IP_1> <PORTAL_IP_2> <PORTAL_IP_3> <PORTAL_IP_4>; do
    sudo nvme discover -t tcp -a "$portal" -s 4420 \
                       --host-traddr <HOST_IP> \
                       --persistent --ctrl-loss-tmo=-1
done

# Verify - this must be non-zero, or automatic recovery cannot happen
sudo nvme list-subsys | grep -c discovery
```

Run this once per host interface, so each interface keeps its own discovery
controllers. The same flags belong in `/etc/nvme/discovery.conf` (step 1) so the
controllers are recreated at boot rather than only for the current uptime.

With the discovery controllers in place, a subsystem that has been torn down comes
back on its own: `udev` raises the discovery-log-change event, `nvmf-connect@`
runs, and the I/O controllers are re-established without anyone logging in. In
testing this took roughly 20 seconds from connectivity returning.

> **Automatic reconnect restores the storage, not the workload.** Once paths return
> you may still need to remount filesystems, restart VMs, rescan LVM volume groups
> or restart applications. The namespace can also return on a **different device
> node** (for example `nvme0n1` becoming `nvme0n2`), so always reference volumes by
> a stable path — see below.

**3. Choose `ctrl_loss_tmo` deliberately**

`ctrl_loss_tmo` is a retry *count*, not a wall-clock budget: the kernel converts it
to `ctrl_loss_tmo / reconnect_delay` attempts, and each attempt costs
`reconnect_delay` plus a failed connect. Real tolerance runs roughly a third longer
than the number suggests — the default `600` is about 13 minutes.

| Workload | Setting | Behaviour |
| --- | --- | --- |
| Mounted filesystem, LVM, VM raw-device passthrough | `--ctrl-loss-tmo=-1` | Never gives up, so the subsystem is never removed and an open file descriptor keeps working. I/O queues for the duration of the outage. |
| Kubernetes/CSI, or anything that restarts on I/O error | finite value (default `600`) **plus** persistent discovery controllers from step 2 | Fails in bounded time; the orchestrator reopens the device. |

```bash
# Durable values belong in the connect arguments, not sysfs
sudo nvme connect -t tcp -a <PORTAL_IP> -s 4420 -n <SUBSYSTEM_NQN> \
                  --host-traddr <HOST_IP> --ctrl-loss-tmo=-1
```

> **`ctrl_loss_tmo` written to sysfs does not persist.** After a reconnect the
> controller returns with the default value, silently discarding anything set under
> `/sys/class/nvme/nvmeX/ctrl_loss_tmo`. Set it in the connect arguments,
> `/etc/nvme/discovery.conf`, or `/etc/nvme/config.json`.

**4. Reference namespaces by stable ID**

```bash
ls -l /dev/disk/by-id/nvme-Pure_Storage_FlashArray_*
```

Use these paths in `/etc/fstab`, LVM filters, and VM disk definitions — never
`/dev/nvmeXnY`. The kernel node is not stable across a teardown and reconnect, so
anything pinned to it breaks after a single recovery event even though the storage
is healthy.

**5. Load the fabrics modules at boot**

```bash
sudo tee /etc/modules-load.d/nvme-fabrics.conf > /dev/null <<EOF
nvme_tcp
nvme_fabrics
EOF
```

Some distributions (notably SLES and openSUSE Leap) do not autoload these. Without
them `nvme connect` fails with the misleading error
`Failed to scan topology: No such file or directory`.
