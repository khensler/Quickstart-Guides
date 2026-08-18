### FlashBlade: a validated end-to-end path

NFS over TLS has been verified working against a FlashBlade//S500 on Purity//FB 4.6.9, with
`xprtsec=tls` present in the live mount and a successful `tlshd` handshake. Unlike
FlashArray File Services, the FlashBlade lets you create and bind a certificate that
actually matches the NFS endpoint, which is what makes the client's identity check pass.

> **Important: `xprtsec=tls` in the storage class encrypts the client, it does not secure the
> export.** With generated export rules the array still accepts an unencrypted mount of the
> same volume, so anyone who omits the option — a hand-run `mount`, another cluster, a
> forgotten storage class — reads the same data in the clear. Verified directly: a plaintext
> mount of a volume provisioned this way succeeded and read the file. Treat
> `xprtsec=tls` on its own as *opting in*, not as a control.

**1. Create a certificate whose name matches the data VIP.** The array's default `global`
certificate will not do: it is issued to the array, has no subject alternative names, and
the client rejects it because nothing in it matches the address being mounted. Create a
separate certificate rather than replacing `global`, which the management interface uses.

```bash
purecert self-signed create nfs-tls \
  --common-name <fb-data-vip> --san <fb-data-vip> --days 365 \
  --key-algorithm rsa --key-size 2048

# Confirm the SAN landed -- this is the field that decides whether the client accepts it
purecert list nfs-tls
```

**2. Bind it to the data VIP with its own TLS policy.** Adding a new policy leaves
`default-tls-policy` — and management access — untouched.

```bash
purepolicy tls create px-nfs-tls --appliance-certificate nfs-tls
purepolicy tls add --network-interface <data-vip-interface> px-nfs-tls
purepolicy tls enable px-nfs-tls
purepolicy tls list
```

**3. Require TLS on the export, or the encryption stays optional.** Create an export policy
whose rule mandates transport security, and point the storage class at it with
`pure_nfs_policy`:

```bash
purepolicy nfs create px-tls-required
purepolicy nfs rule add px-tls-required --client '*' --rw --no-squash --tls-required
```

Use `--mutual-tls-required` instead where clients must also present a certificate. Scope
`--client` to the node networks rather than `*` wherever you can.

```yaml
parameters:
  backend: "pure_file"
  pure_nfs_policy: "px-tls-required"      # mutually exclusive with pure_export_rules
mountOptions:
  - nfsvers=4.1
  - xprtsec=tls
```

**4. Trust the certificate on every node**, alongside the packages above:

```bash
sudo cp nfs-tls.crt /usr/local/share/ca-certificates/    # Debian and Ubuntu
sudo update-ca-certificates
# On RHEL and derivatives: /etc/pki/ca-trust/source/anchors/ then update-ca-trust
```

**Verify, and verify the negative case too.** A TLS mount that works proves only that TLS is
possible:

```bash
# The option reached the mount
findmnt -t nfs4 -o SOURCE,OPTIONS | grep xprtsec

# The handshake actually completed
sudo journalctl -u tlshd | tail

# The one people skip: prove plaintext is refused
sudo mount -t nfs -o vers=4.1 <fb-data-vip>:/<export> /mnt/test
```

With the export policy above, that last command fails with
`mount.nfs: Operation not permitted` — which is the result you want. If it succeeds, TLS is
merely available on that volume, not required, and the storage class is the only thing
keeping traffic encrypted.

> **Note:** Trusting the array's self-signed leaf certificate works, but `tlshd` logs
> `audit: There was a non-CA certificate in the trusted list`. It is a warning, not a
> failure. For anything beyond a lab, issue the certificate from your own CA — use
> `purecert csr` to generate a signing request instead of `purecert self-signed create` —
> and distribute the CA rather than the leaf.
