Getting the bond up is not the same as getting NFS onto it. The mount is made by the
node's kernel using the node's routing table, so the endpoint has to be reachable
*through the storage interface* — not merely reachable. Those are different tests, and
only one of them is usually run.

Both a layer 2 and a layer 3 design work. Pick one deliberately, and know which one you
have:

| Design | NFS endpoint | Route needed |
|---|---|---|
| **Layer 2, same subnet** — recommended | on the storage VLAN, in the same subnet as the node's storage address | none — the endpoint is link-local to the storage interface |
| **Layer 3, routed** — supported | on a different subnet, reached through a router on the storage VLAN | an explicit route per endpoint, plus a router that actually routes it |

Layer 2 is the recommendation: it keeps the router out of the data path, needs no per-node
route configuration, and cannot be silently bypassed. Where the storage network is already
routed, or the array and the nodes cannot share a subnet, **layer 3 will function** —
routed NFS is a normal deployment, not a workaround.

What layer 3 costs depends entirely on the physical network between the nodes and the
array. Each hop adds latency, and NFS is sensitive to it: latency shows up as lower IOPS
at the same queue depth long before it shows up as an error. The router also becomes part
of the storage path, so its forwarding capacity, buffer depth, and MTU handling now bound
your throughput, and its failure domain now includes your storage. Two specific things to
check on a routed design:

- **MTU end to end through the router**, not just node-to-switch. A router hop that
  fragments or drops 9000-byte frames undoes jumbo frames for the whole path.
- **Whether the path is symmetric.** Asymmetric routing between the node and the array
  produces intermittent stalls that are painful to diagnose and easy to blame on the
  array.

Where throughput or latency targets are tight, keep the array and the nodes on the same
layer 2 segment and remove the variable.

> **Important:** A storage VLAN is frequently a layer-2-only segment with no router,
> even when an address like `x.x.x.1` answers ping. Confirm before designing around it:
> a gateway that replies to ICMP for itself may still route nothing. Test with a
> destination *off* the storage subnet, bound to the storage interface.

**The failure mode to watch for** is a layer 3 design that was never finished. If the
storage subnet is link-scoped and the NFS endpoint lives on another subnet, the node has
no route to it through the storage interface, so the kernel falls back to the default
route and mounts over the management network instead. The bond is up, the addresses and
MTU are correct, and the endpoint pings — every check below passes — while no NFS traffic
touches the storage network at all. Throughput and failover then reflect the management
path, and nothing reports an error. This is not layer 3 performing poorly; it is layer 3
not being used, with the management network silently substituted for it.

**How to measure it correctly.** Ask the routing table which interface is chosen:

```bash
ip route get <nfs-endpoint>
```

The reply names the egress device and source address. It must be the storage interface
and the storage address.

> **Important:** Do not test this by setting a source address. `ping -I <address>` and a
> socket `bind()` set the *source address only* — the packet still leaves by whichever
> interface the routing table selects, and asymmetric replies make an unusable path look
> healthy. To force the interface, use `ping -I <interface-name>` with a device name, or
> `SO_BINDTODEVICE`. This is the single easiest way to convince yourself a storage path
> works when it does not.
