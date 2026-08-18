> **Important:** LACP aggregates bandwidth across flows, not within one. It is a redundancy feature first and a throughput feature second. Size the design around a single member link, not around the bond total.

A bond distributes traffic by hashing each flow to exactly one member link. The hash is computed once per connection, so every packet of a given TCP connection leaves through the same NIC for the life of that connection. The consequences are worth stating plainly:

- **One TCP connection never exceeds one member link.** Two bonded 25 GbE NICs do not give a single NFS mount 50 GbE. They give it 25 GbE, with a second link standing by for other flows and for failure.
- **A default NFS mount is one connection.** Without `nconnect`, a mount opens a single TCP connection to the NFS endpoint, so it lands on one link and stays there. The second NIC carries none of that mount's traffic.
- **The hash is not a scheduler.** Distribution is statistical, not balanced. Several connections can hash onto the same link while another sits idle, and nothing rebalances them afterward. Aggregate throughput improves with more connections but is never guaranteed to be even.
- **Layer 2 hashing defeats the purpose here.** With the default `layer2` policy, the hash uses MAC addresses only. Every node reaches the same array VIP through the same next-hop MAC, so all traffic to that endpoint pins to one link no matter how many connections exist. Use `layer3+4` so source and destination ports enter the hash and separate connections can diverge.
- **Both ends must agree.** LACP is negotiated. The switch needs a matching port-channel, and a bond spanning two switches needs MLAG, VPC, or the vendor equivalent. A bond configured on the host against non-channeled switch ports produces flapping, duplicate frames, or a silently degraded link rather than a clean failure.

To actually use the second link for a single workload, raise the connection count with `nconnect` in the storage class `mountOptions`. That is what turns a one-link mount into several connections that the hash can spread. For sustained throughput beyond one link on FlashBlade, prefer scaling out data VIPs over trying to force a single VIP through a wider bond.

If aggregation is not the goal, `active-backup` bonding is the honest alternative: identical redundancy, no hashing surprises, no switch-side port-channel required, and a bandwidth ceiling of one link that is obvious to everyone reading the configuration.
