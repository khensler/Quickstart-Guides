Two separate things are needed: connections that come back **at boot**, and
connections that come back **after a path failure**. `nvmf-autoconnect.service` only
does the first — it is a one-shot that runs at boot, not a reconnect daemon.

**1. Reconnect at boot**

```bash
# Discovery configuration - list EVERY array this host uses
sudo tee /etc/nvme/discovery.conf > /dev/null <<EOF
-t tcp -a <PORTAL_IP_1> -s 4420 --host-traddr <HOST_IP_1>
-t tcp -a <PORTAL_IP_2> -s 4420 --host-traddr <HOST_IP_1>
-t tcp -a <PORTAL_IP_3> -s 4420 --host-traddr <HOST_IP_2>
-t tcp -a <PORTAL_IP_4> -s 4420 --host-traddr <HOST_IP_2>
EOF

sudo systemctl enable --now nvmf-autoconnect.service
```

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
