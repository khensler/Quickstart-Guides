Configure these on the array **before** creating a storage class. PX-CSI creates the
managed directory and its export; everything below it must already exist.

| Requirement | Why | Where |
|---|---|---|
| **File Services enabled**, with the Default Array Server created | PX-CSI provisions into an existing file server | [Setting Up File Services on FlashArray](https://support.everpuredata.com/r/flasharray-file-services/setting-up-file-services-68d), [Creating a New File Server Using the File Server Wizard](https://support.everpuredata.com/r/flasharray-file-services/creating-a-new-file-server-using-the-file-server-wizard) |
| **File VIF**, reachable from every node | the NFS endpoint clients mount. Built across both controllers, so it survives port and controller failure | [Setting Up File Services on FlashArray](https://support.everpuredata.com/r/flasharray-file-services/setting-up-file-services-68d) |
| **Parent file system** | the driver creates directories inside it; it cannot create the file system | [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services) |
| **NFS export policy**, permitting the node networks and the NFS version your storage class requests | the array policy overrides `mountOptions` — ask for a version it does not permit and the mount fails | [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services) |
| **Quota policy** (optional but recommended) | without one the PVC size is advisory and a directory can consume the whole parent file system | [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services) |
| **API token** for an account that can manage file objects | goes in `pure.json` | [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services/flasharray-file-services) |
| **Certificate with a SAN covering the NFS endpoint** — *only for `xprtsec=tls`* | the client verifies the certificate against the address it mounts by. See the TLS requirements below before planning this | [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services) |

Verify what the array actually has before troubleshooting the driver:

```bash
purefs list                      # parent file systems
purenetwork eth list --service file   # File VIFs — confirm one exists and is enabled
purepolicy nfs list              # export policies and the NFS versions each permits
purepolicy nfs rule list         # client rules: which networks, squash, version
purepolicy quota list            # quota policies
purecert list --uses             # certificates and the services consuming them
```

Two array-side network requirements that are easy to miss and expensive to unwind:

- **Keep client traffic on a different IP network from management.** Pure recommends this
  explicitly, and by default the array sends DNS lookups out the management interface
  rather than the file VIF.
- **Do not use overlapping address spaces.** Purity treats IP networks with identical or
  overlapping ranges as one address range, and traffic can leave the wrong interface. A
  management VIF on `192.168.0.0/22` alongside a file VIF on `192.168.1.0/23` is the
  documented failure case; distinct, non-overlapping subnets are fine.

The [FlashArray File Services documentation](https://support.everpuredata.com/r/flasharray-file-services)
is authoritative for all of the above, including the file VIF bonding choices (physical
pairing versus LACP, which requires switch support for IEEE 802.3ad) and the File
Services-specific DNS and directory-services configuration.
