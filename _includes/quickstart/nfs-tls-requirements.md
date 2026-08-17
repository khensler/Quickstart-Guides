NFS over TLS has requirements on both sides of the connection, and the client side is the one people miss.

**Array side:**

| Array | Minimum Purity |
|---|---|
| FlashArray File Services | Purity//FA 6.10.6 |
| FlashBlade | Purity//FB 4.6.0 |

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
