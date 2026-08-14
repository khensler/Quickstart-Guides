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

> **Important:** Kernel TLS offload is fully supported by Red Hat *for use with NFS over TLS*. Other uses of kTLS remain Technology Preview. Do not read the general kTLS support state as ruling out NFS over TLS — the NFS case is carved out and supported from RHEL 9.6 onward, and conversely, do not treat an NFS-over-TLS deployment as blanket approval for kTLS elsewhere on those nodes.

On a distribution older than RHEL 9.6, or on a non-RHEL distribution, confirm both the support state and the package availability before committing to TLS. Package presence alone is not the same as a supported configuration.
