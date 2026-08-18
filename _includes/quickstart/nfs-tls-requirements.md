NFS over TLS has requirements on both sides of the connection, and the client side is the one people miss.

**Array side:**

| Array | Minimum Purity |
|---|---|
| FlashArray File Services | Purity//FA 6.10.6 |
| FlashBlade | Purity//FB 4.6.0 |

**The two platforms are not equally ready, and the difference is the certificate.** A client
verifies the server's identity against the address it mounted, so the array must present a
certificate naming that address. On FlashBlade you can create one; confirm you can before
planning a FlashArray File Services TLS rollout:

| | FlashBlade | FlashArray File Services |
|---|---|---|
| Create a certificate naming the NFS endpoint | `purecert self-signed create <name> --common-name <vip> --san <vip>` | No equivalent — the default certificate has no CN or SAN matching the file VIF |
| Bind it to the NFS-serving address | `purepolicy tls create` + `purepolicy tls add --network-interface` | `purepolicy tls` absent on 6.10.6; REST `policies/tls` from 2.54 |
| Require TLS on the export | `purepolicy nfs rule add --tls-required` | Not exposed |
| Verified end to end | **Yes** — Purity//FB 4.6.9 | Not achieved |

On FlashArray, 6.10.6 introduces a **`tls` policy type** that ties a certificate, the TLS
version and cipher constraints, and the protocols TLS is enforced for to a file server.
Where you can configure it depends on the release, which is the detail that costs people
time:

| Purity//FA | REST `policies/tls` | CLI `purepolicy tls` |
|---|---|---|
| 6.10.6 | Yes, at **API 2.54 or later** | **Not available** |
| 6.12.0 | Yes | Yes |

- **On 6.10.6, configure TLS from the GUI or REST — not the CLI.** `purepolicy tls` is
  rejected as an invalid subcommand; the subcommand arrives in 6.12.0. `purecert` manages
  certificates on both releases but cannot bind one to a file server.
- **Pin REST 2.54 or later.** The `policies/tls` endpoint does not exist at 2.53 and
  below, so a client pinned to an older API version gets a bare `404 Not found` with no
  hint that the API version is the problem — easily misread as the release lacking the
  feature. Check `https://<array>/api/api_version` for the array's maximum.
- Note that `purepolicy`'s own manual page does not document the `tls` subcommand on
  either release, so `pureman purepolicy` is not a reliable way to tell whether it exists.

The certificate the policy presents must carry the **file VIF address in its subject
alternative names**, since that is the name the client connects to and verifies.

**Client side:**

| Requirement | Detail |
|---|---|
| Operating system | NFS over TLS (RFC 9289) is fully supported as of RHEL 9.6 and RHEL 10.0. It was an unsupported Technology Preview in RHEL 9.4 and 9.5. |
| Packages | `nfs-utils`, `ktls-utils` (which provides `tlshd`), and `openssl` on every node that mounts the volume. |
| Kernel module | `ktls.ko`, providing kernel TLS offload. |
| **Certificate trust** | Every node must trust the signer of the array's NFS TLS certificate. This is a separate requirement from the packages, and it is the one most likely to be missed. |

**Certificate trust is not optional, and its failure is disguised.** `tlshd` ships with
empty `[authenticate]`, `[authenticate.client]` and `[authenticate.server]` sections in
`/etc/tlshd.conf`, so it falls back to the system trust store. If the array's certificate
signer is not there, the TLS handshake fails and **NFS reports the failure as an access
problem, not a certificate problem**:

```
mount.nfs: access denied by server while mounting <endpoint>:/<export>
```

That wording points at export rules and squash settings, which will waste your time. The
real cause appears only in the handshake daemon's log:

```bash
journalctl -u tlshd
# Certificate signer not found.
# Certificate owner unexpected.
# Handshake with '<nfs-endpoint>' failed
```

> **Important:** Make `journalctl -u tlshd` your first check for any `xprtsec=tls` mount
> failure, before looking at export rules. A daemon that is installed, `active` and
> `enabled` still cannot complete a handshake it has no trust anchor for — running is
> necessary but not sufficient.

Point `tlshd` at the right trust anchor by setting `x509.truststore` under
`[authenticate.client]` in `/etc/tlshd.conf`, or by adding the array's CA to the system
trust store. On an immutable node such as Red Hat CoreOS, that file has to be delivered
by MachineConfig rather than edited in place.

> **Important:** Kernel TLS offload is fully supported by Red Hat *for use with NFS over TLS*. Other uses of kTLS remain Technology Preview. Do not read the general kTLS support state as ruling out NFS over TLS — the NFS case is carved out and supported from RHEL 9.6 onward, and conversely, do not treat an NFS-over-TLS deployment as blanket approval for kTLS elsewhere on those nodes.

On a distribution older than RHEL 9.6, or on a non-RHEL distribution, confirm both the support state and the package availability before committing to TLS. Package presence alone is not the same as a supported configuration.
