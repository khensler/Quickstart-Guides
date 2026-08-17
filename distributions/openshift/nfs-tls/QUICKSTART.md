---
layout: default
title: Installing ktls-utils on Red Hat CoreOS by Layering an RHCOS Image
---

# Installing ktls-utils on Red Hat CoreOS by Layering an RHCOS Image

---

{% include quickstart/disclaimer.md %}

---

## Overview

NFS over TLS (RFC 9289) needs a handshake daemon, `tlshd`, running on every node that
mounts an encrypted export. `tlshd` comes from the `ktls-utils` package, and **Red Hat
CoreOS does not ship it**. The kernel half of the feature is present; the user-space
half is not.

`ktls-utils` is also not one of the supported RHCOS extensions, so it cannot be added
with a `MachineConfig` `spec.extensions` entry. Delivering it means **layering a custom
RHCOS image**, which replaces the node's boot image and reboots the node.

This guide covers both layering paths, verification, and the failure modes worth knowing
before you schedule the work.

> **Note:** This is node preparation, not storage configuration. It is a prerequisite
> for `xprtsec=tls` mounts but is independent of any particular storage backend. For the
> NFS provisioning it enables, see the
> [OpenShift NFS Quickstart](../nfs/QUICKSTART.md).

> **Scope:** Red Hat CoreOS on OpenShift. On a general-purpose Linux node, `ktls-utils`
> installs from the distribution package manager and none of this applies — see the
> [Kubernetes NFS Quickstart](../../kubernetes/nfs/QUICKSTART.md).

---

## Prerequisites

- An OpenShift cluster with `cluster-admin` access through `oc`.
- OpenShift 4.19 or later. Earlier releases sit on an RHCOS base below RHEL 9.6, where
  NFS over TLS is Technology Preview and layering will not make it supported.
- A **RHEL entitlement**, because `ktls-utils` comes from RHEL AppStream rather than
  from the RHCOS image. A cluster with Simple Content Access already holds one — check
  `oc get secret etc-pki-entitlement -n openshift-config-managed`.
- A container registry the cluster can pull from. The internal registry works, but only
  when it is `Managed` with storage configured.
- **The CA that signed your array's NFS TLS certificate.** Installing the package is only
  half the job: without a trust anchor the handshake fails and the mount is refused. See
  [Step 7](#step-7-trust-the-arrays-certificate).
- A maintenance window. The machine config pool rolls nodes one at a time; on a
  single-node cluster the API disappears during the reboot.

---

## Background

NFS over TLS splits across the kernel and user space, and RHCOS ships only one half:

| Component | Provided by | In RHCOS? |
|---|---|---|
| `tls.ko` kernel module | the RHCOS kernel | **Yes** |
| `tlshd` handshake daemon | the `ktls-utils` package | **No** |

Without `tlshd`, the kernel raises a handshake request that nothing answers, so a mount
carrying `xprtsec=tls` fails even though every version requirement is met.

The RHEL floor per OpenShift release, which governs the kernel side only:

| OpenShift release | RHCOS base | Kernel-side TLS |
|---|---|---|
| 4.22 | RHEL 9.8 | Supported |
| 4.21 | RHEL 9.6 | Supported |
| 4.20 | RHEL 9.6 | Supported |
| 4.19 | RHEL 9.6 | Supported |
| 4.18 | RHEL 9.4 | Technology Preview — not supported |
| 4.16 | RHEL 9.4 | Technology Preview — not supported |
| 4.14 | RHEL 9.2 | Not available |

The RHEL minor version is fixed per OpenShift minor version, so moving from RHEL 9.4 to
9.6 means an OpenShift minor upgrade, not a z-stream update.

Treat the version floor and the package delivery as two separate gates. Clearing RHEL
9.6 says the kernel supports TLS; it says nothing about whether `tlshd` is on the node.

---

## Step 1: Confirm the gap on your own cluster

```bash
oc debug node/<node-name> -- chroot /host bash -c \
  'rpm -q ktls-utils; systemctl list-unit-files "tlshd*"; ls -l /usr/sbin/tlshd'
```

On a stock cluster expect `package ktls-utils is not installed`, `0 unit files listed`,
and no such file.

> **Important:** Do not test this with `systemctl is-active tlshd` alone. For a unit that
> does not exist, `systemctl is-active` prints `inactive` — the same answer it gives for
> a unit that is installed but stopped. Reading that output left to right invites the
> conclusion that the daemon is merely stopped. Use `rpm -q ktls-utils` or
> `systemctl list-unit-files` to tell the two apart.

Confirm the kernel side is present, since layering cannot supply it:

```bash
oc debug node/<node-name> -- chroot /host bash -c 'modinfo tls | head -1'
```

---

## Step 2: Confirm you cannot use an extension

`ktls-utils` is not an available RHCOS extension. The supported set is `two-node-ha`,
`ipsec`, `usbguard`, `kerberos`, `kernel-devel`, `sandboxed-containers`, and `sysstat`.

> **Warning:** A `MachineConfig` naming `ktls-utils` under `spec.extensions` is
> **accepted by the API server** — extensions are not validated there — and then fails
> at render time, leaving the machine config pool `DEGRADED`. Do not try it to find out.

---

## Step 3: Choose a layering path

| Path | Use when | Trade-off |
|---|---|---|
| **On-cluster** ([Step 4](#step-4-on-cluster-layering)) | the cluster can build and push for itself | Blocked on clusters whose image signature policy the build cannot satisfy — see the warning in Step 4 |
| **Out-of-cluster** ([Step 5](#step-5-out-of-cluster-layering)) | on-cluster is blocked, or you already have a build pipeline | You supply the build host, and the image is yours to rebuild after each OpenShift upgrade |

Both produce the same result: a layered image the pool boots. Try on-cluster first; it
needs no external infrastructure.

---

## Step 4: On-cluster layering

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineOSConfig
metadata:
  name: worker                        # must equal the pool name below
spec:
  machineConfigPool:
    name: worker                      # the pool whose nodes mount TLS volumes
  imageBuilder:
    imageBuilderType: Job
  baseImagePullSecret:
    name: <base-image-pull-secret>    # in openshift-machine-config-operator
  renderedImagePushSecret:
    name: <push-secret>
  renderedImagePushSpec: <registry>/<repo>/rhcos-ktls:latest
  containerFile:
    - containerfileArch: NoArch
      content: |
        FROM configs AS final
        RUN dnf -y install ktls-utils && \
            dnf clean all && \
            systemctl enable tlshd.service && \
            ostree container commit
```

Before applying it:

- **The `MachineOSConfig` name must equal the `machineConfigPool` name**, and there can
  be only one per pool. A descriptive name is rejected with
  `MachineOSConfig name must match the referenced MachineConfigPool name`.
- `renderedImagePushSecret` must be the **builder service account's own auto-generated
  secret** in `openshift-machine-config-operator`, not a hand-made copy. That namespace
  prunes foreign secrets within about a minute. Find the right name with:

  ```bash
  oc get secrets -n openshift-machine-config-operator \
    -o jsonpath='{.items[?(@.metadata.annotations.openshift\.io/internal-registry-auth-token\.service-account=="builder")].metadata.name}{"\n"}'
  ```

- Confirm the registry has somewhere to push. A cluster whose image registry is
  `Removed` has no storage:

  ```bash
  oc get configs.imageregistry.operator.openshift.io cluster \
    -o jsonpath='{.spec.managementState}{"\n"}'
  ```

- Make the RHEL entitlement available to the build, otherwise `dnf` cannot see AppStream
  and the build fails resolving `ktls-utils`.
- `systemctl enable tlshd.service` in the build matters. Installing the package alone
  leaves the daemon disabled, which reproduces the original failure having already spent
  a reboot.

Watch the build and the rollout:

```bash
oc get machineosbuild
oc get mcp
oc get machineconfignodes
```

> **Important:** The on-cluster build can fail while *pulling the base image*, with
> `Source image rejected: A signature was required, but no signature exists` and the
> build pod's init container exiting 125. This is a signature-verification interaction,
> not a problem with your Containerfile. Clusters ship a default `ClusterImagePolicy`
> named `openshift` requiring Red Hat signatures for
> `quay.io/openshift-release-dev/ocp-release` and the `ocp-v4.0-art-dev` /
> `ocp-v5.0-art-dev` scopes. Nodes satisfy it because they also carry
> `/etc/containers/registries.d/sigstore-registries.yaml`, which tells the container
> tooling to fetch sigstore attachments from the registry. The build pod mounts the
> *policy* and `registries.conf` but not `registries.d`, so it enforces the requirement
> without knowing where to look.
>
> ```bash
> oc get clusterimagepolicy openshift -o jsonpath='{.spec.scopes}{"\n"}'
> oc logs -n openshift-machine-config-operator <build-pod> -c image-build | tail -20
> ```
>
> Deleting the policy is not a workaround — it carries
> `include.release.openshift.io/self-managed-high-availability`, so the Cluster Version
> Operator recreates it. Use [Step 5](#step-5-out-of-cluster-layering) instead.
>
> A failed build leaves the pool `DEGRADED` until you remove the `MachineOSConfig`.
> `oc delete machineosconfig <name>` reverts the pool to the stock image and clears it.

---

## Step 5: Out-of-cluster layering

This path avoids the signature check entirely: `podman` on an ordinary build host has no
`ClusterImagePolicy`, so it pulls the RHCOS base normally. Push the result into the
cluster's own registry and point the pool at it.

### Gather the inputs

```bash
# The exact base image to layer on top of
oc get machineconfig "$(oc get mcp master -o jsonpath='{.spec.configuration.name}')" \
  -o jsonpath='{.spec.osImageURL}{"\n"}'

# Expose the internal registry so an outside host can push to it
oc patch configs.imageregistry.operator.openshift.io cluster \
  --type=merge -p '{"spec":{"defaultRoute":true}}'
oc get route default-route -n openshift-image-registry -o jsonpath='{.spec.host}{"\n"}'

# A service account that may push
oc create sa image-pusher -n openshift-machine-config-operator
oc policy add-role-to-user registry-editor -z image-pusher -n openshift-machine-config-operator
oc create token image-pusher -n openshift-machine-config-operator --duration=6h
```

Take the entitlement certificates from the cluster:

```bash
oc get secret etc-pki-entitlement -n openshift-config-managed \
  -o go-template='{{index .data "entitlement.pem" | base64decode}}' > entitlement/entitlement.pem
oc get secret etc-pki-entitlement -n openshift-config-managed \
  -o go-template='{{index .data "entitlement-key.pem" | base64decode}}' > entitlement/entitlement-key.pem
```

> **Note:** Enabling `defaultRoute` triggers an `openshift-apiserver` rollout. On a
> single-node cluster the replacement pod cannot schedule until the old one has gone, so
> the route and OAuth APIs are briefly unavailable. It clears on its own.

### Supply the repository definition

RHCOS carries no `/etc/yum.repos.d` entries, so the build must provide one alongside the
certificates:

```ini
# redhat.repo
[rhel-9-appstream]
name=RHEL 9 AppStream
baseurl=https://cdn.redhat.com/content/dist/rhel9/9/x86_64/appstream/os
enabled=1
gpgcheck=1
gpgkey=file:///etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release
sslverify=1
sslcacert=/etc/rhsm/ca/redhat-uep.pem
sslclientcert=/etc/pki/entitlement/entitlement.pem
sslclientkey=/etc/pki/entitlement/entitlement-key.pem
```

> **Important:** `sslcacert=/etc/rhsm/ca/redhat-uep.pem` is required.
> `cdn.redhat.com` presents a certificate issued by Red Hat's *Entitlement Operations
> Authority*, not a publicly trusted CA, so ordinary trust stores reject it. A plain
> `curl https://cdn.redhat.com` returns nothing at all, which reads as "unreachable" and
> sends you looking for a firewall problem that does not exist. Add `-k` and it answers
> `403`, which is the correct response to a request with no client certificate. The CA
> already ships in the RHCOS base at that path.

### Build

```dockerfile
FROM <base-osImageURL> AS final

COPY entitlement/entitlement.pem entitlement/entitlement-key.pem /etc/pki/entitlement/
COPY redhat.repo /etc/yum.repos.d/redhat.repo

RUN dnf -y install ktls-utils && \
    dnf clean all && \
    systemctl enable tlshd.service && \
    rpm -q ktls-utils && \
    test -x /usr/sbin/tlshd && \
    rm -f /etc/yum.repos.d/redhat.repo \
          /etc/pki/entitlement/entitlement.pem \
          /etc/pki/entitlement/entitlement-key.pem && \
    ostree container commit
```

> **Warning:** Delete the entitlement certificates and the repo file in the **same `RUN`
> layer** that uses them. A `COPY` in one layer and an `rm` in a later one leaves the
> credentials recoverable from the image history. Confirm before pushing:
>
> ```bash
> podman run --rm --entrypoint /bin/bash <image> -c 'ls /etc/pki/entitlement/'
> ```
>
> It should print nothing.

```bash
podman build --authfile <pull-secret.json> --tag rhcos-ktls:local .

# Verify the package landed and the unit is enabled, before spending a reboot
podman run --rm --entrypoint /bin/bash rhcos-ktls:local -c \
  'rpm -q ktls-utils; test -x /usr/sbin/tlshd && echo present; systemctl is-enabled tlshd'

podman login --tls-verify=false -u image-pusher -p <token> <registry-route>
podman push --tls-verify=false rhcos-ktls:local \
  <registry-route>/openshift-machine-config-operator/rhcos-ktls:latest
```

`--tls-verify=false` covers only the route's ingress certificate, which an outside build
host has no reason to trust. The nodes still pull over a trusted internal path.

### Roll it out

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-master-osimage-ktls
  labels:
    machineconfiguration.openshift.io/role: master
spec:
  # The INTERNAL service DNS, not the external route. Nodes trust the internal
  # registry through the node-ca daemonset, and this reference is outside the
  # ClusterImagePolicy scopes, so the default accept-anything rule applies.
  osImageURL: image-registry.openshift-image-registry.svc:5000/openshift-machine-config-operator/rhcos-ktls:latest
```

The node reboots. Watch it with `oc get mcp` and `oc get machineconfignodes` until the
pool reports `UPDATED=True` and `DEGRADED=False`.

---

## Step 6: Verify

Confirm the node booted your image rather than the release image:

```bash
oc debug node/<node-name> -- chroot /host rpm-ostree status --booted
```

The `BootedDeployment` line should name your registry reference.

Then confirm the daemon:

```bash
oc debug node/<node-name> -- chroot /host bash -c \
  'rpm -q ktls-utils; systemctl is-active tlshd; systemctl is-enabled tlshd; ls -l /etc/tlshd.conf'
```

Expect `ktls-utils-<version>`, `active`, `enabled`, and a present `/etc/tlshd.conf`.

> **Important:** Those four are **necessary but not sufficient.** A `tlshd` that is
> installed, active and enabled still cannot complete a handshake it has no trust anchor
> for. Finish [Step 7](#step-7-trust-the-arrays-certificate) before adding `xprtsec=tls`
> to a storage class.

---

## Step 7: Trust the array's certificate

`/etc/tlshd.conf` ships with empty `[authenticate]`, `[authenticate.client]` and
`[authenticate.server]` sections, so `tlshd` falls back to the system trust store. If the
signer of the array's NFS TLS certificate is not there, every handshake fails.

**The symptom is disguised.** NFS reports a trust failure as an access problem:

```
mount.nfs: access denied by server while mounting <endpoint>:/<export>
```

which points at export rules and squash settings — the wrong place entirely. The real
cause is only in the daemon's log:

```bash
oc debug node/<node-name> -- chroot /host journalctl -u tlshd -n 20
```

```
tlshd[…]: Certificate signer not found.
tlshd[…]: Certificate owner unexpected.
tlshd[…]: Handshake with '<nfs-endpoint>' failed
```

> **Important:** Make `journalctl -u tlshd` the **first** check for any `xprtsec=tls`
> mount failure, before looking at export rules or NFS policies.

Point `tlshd` at a trust anchor by setting `x509.truststore` under `[authenticate.client]`.
On Red Hat CoreOS the node is immutable, so both the CA bundle and the configuration must
arrive by MachineConfig:

```yaml
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  name: 99-worker-tlshd-truststore
  labels:
    machineconfiguration.openshift.io/role: worker
spec:
  config:
    ignition:
      version: 3.4.0
    storage:
      files:
        - path: /etc/pki/tlshd/array-ca.pem
          mode: 0644
          overwrite: true
          contents:
            # Replace with your array's CA, base64-encoded
            source: data:text/plain;charset=utf-8;base64,<base64-of-array-ca.pem>
        - path: /etc/tlshd.conf
          mode: 0644
          overwrite: true
          contents:
            source: data:text/plain;charset=utf-8;base64,<base64-of-tlshd.conf>
```

where the `tlshd.conf` you encode contains:

```ini
[debug]
loglevel=0
tls=0
nl=0

[authenticate]

[authenticate.client]
x509.truststore= /etc/pki/tlshd/array-ca.pem

[authenticate.server]
```

Raising `loglevel` and `tls` in the `[debug]` section while first bringing TLS up makes
the handshake failure far easier to read; lower them again afterwards.

Applying this reboots the pool, like any MachineConfig. Afterwards, confirm the trust
store is in place and retry a TLS mount:

```bash
oc debug node/<node-name> -- chroot /host bash -c \
  'grep -A1 authenticate.client /etc/tlshd.conf; ls -l /etc/pki/tlshd/'
```

> **Note:** Mutual TLS (`xprtsec=mtls`) additionally needs a client certificate and key,
> set with `x509.certificate` and `x509.private_key` under `[authenticate.client]`. Get
> one-way TLS working first — an mTLS failure looks identical from the NFS side.

### The array's certificate has to be usable, not just trusted

Trusting the certificate the array already presents is often **not enough**, and it is
worth understanding why before spending a reboot on it. A trust anchor has to satisfy two
separate checks, and `tlshd` reports them separately:

| `tlshd` message | Check | Fixed by |
|---|---|---|
| `Certificate signer not found` | Is the signer trusted? | adding the signer to the truststore — a client-side fix |
| `Certificate owner unexpected` | Does the certificate name match the endpoint? | **only a certificate the array presents with a matching name** |

Installing the array's own certificate clears the first and leaves the second untouched.
Trusting a certificate does not give it a name.

Two properties disqualify a general-purpose appliance certificate from serving here:

- **No `subjectAltName` for the NFS endpoint.** You mount by File VIF address, so the
  certificate needs that address (or a resolvable name you mount by) in its SAN.
  A certificate with no CN and no SAN can never pass hostname verification.
- **It is a leaf, not a CA.** Adding one to a truststore makes `tlshd` log
  `audit: There was a non-CA certificate in the trusted list`. It may load, but it is not
  a legitimate trust anchor.

Check before you plan the work:

```bash
# What the array holds, and which service uses it
purecert list
purecert list --uses
```

You need a certificate whose SAN covers the NFS endpoint and which is issued by a CA you
can distribute to the nodes. Confirm your Purity release lets you bind one to the file
service — some releases expose no NFS-TLS certificate binding at all, in which case the
only certificate in play is the array-wide management certificate, which is unsuitable for
the reasons above and disruptive to replace.

```bash
# Does this release expose TLS policy management at all?
purepolicy tls list
# `invalid choice: 'tls'` means it does not, and no certificate can be bound to NFS.
```

Array-side certificate and file-service configuration is documented separately, and it is
the authority for what your release supports:

- [FlashArray File Services](https://support.everpuredata.com/r/flasharray-file-services) — the bundle, including certificate handling and file-service configuration
- [Setting Up File Services on FlashArray](https://support.everpuredata.com/r/flasharray-file-services/setting-up-file-services-68d) — file VIF, file-specific DNS, directory services
- [Creating a New File Server Using the File Server Wizard](https://support.everpuredata.com/r/flasharray-file-services/creating-a-new-file-server-using-the-file-server-wizard)

> **Note:** Treat the Purity version floor for NFS over TLS as two separate questions.
> One is whether the protocol is *supported* on your release; the other is whether that
> release gives you any way to *bind a suitable certificate* to the file service. They are
> not necessarily the same version, so confirm the second against the array documentation
> and your support matrix before committing to a TLS rollout.

> **Warning:** Do not reach for the array's management certificate as a shortcut. It also
> serves the GUI and REST API, its private key is generally not exportable, so the change
> cannot be cleanly reverted, and on an array with VASA registrations or other certificate
> consumers it has a blast radius well beyond NFS.

---

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Build fails pulling the base image: `A signature was required, but no signature exists` | The default `ClusterImagePolicy` requires signatures and the build pod lacks `registries.d` | Build out of cluster per [Step 5](#step-5-out-of-cluster-layering). Deleting the policy does not persist — the CVO recreates it. |
| Machine config pool goes `DEGRADED` after adding an extension | `ktls-utils` named in `spec.extensions`, which is accepted by the API server but invalid at render time | Remove that `MachineConfig`. Use layering, not extensions. |
| `MachineOSConfig` rejected on creation | Its name does not match the pool name, or one already exists for the pool | Name it exactly as the pool. One per pool. |
| Build fails resolving `ktls-utils` | No RHEL entitlement, no `redhat.repo`, or `sslcacert` missing from it | Supply all three. Remember `cdn.redhat.com` needs `/etc/rhsm/ca/redhat-uep.pem`, not a public CA. |
| Push to the internal registry fails | The registry is `Removed`, or the push secret is a hand-made copy that was pruned | Give the registry storage and set it `Managed`; use the builder service account's own secret. |
| `rpm -q ktls-utils` succeeds but mounts still fail | The package installed with the unit left disabled | `systemctl is-enabled tlshd`. Add `systemctl enable tlshd.service` to the build and rebuild. |
| Everything installed and `active`, but mounts fail with `access denied by server` | The node does not trust the signer of the array's NFS TLS certificate. The NFS layer reports a trust failure as an access failure, which points at export rules instead | `journalctl -u tlshd` — `Certificate signer not found` confirms it. Set `x509.truststore` per [Step 7](#step-7-trust-the-arrays-certificate). Do not start by changing export rules or NFS policies. |
| `systemctl is-active tlshd` says `inactive` and the package is absent | The unit does not exist at all, and `is-active` cannot distinguish that from stopped | Check `rpm -q ktls-utils` or `systemctl list-unit-files "tlshd*"`. |
| TLS mounts worked, then stopped after a node replacement or cluster upgrade | The node booted an unlayered image | Confirm the `MachineOSConfig` or `osImageURL` `MachineConfig` still exists, then re-check `oc get mcp`. After an upgrade rebases the base image, rebuild the layer. |
| API unavailable while exposing the registry route | Single-node cluster: the `openshift-apiserver` replacement pod cannot schedule until the old one terminates | Wait. It clears without intervention. |

---

## Additional Notes

**The layer is not a one-off task.** The daemon arrives in the boot image, so a node that
rejoins the pool on an unlayered image loses `tlshd` and stops mounting TLS volumes. Keep
the `MachineOSConfig` or `osImageURL` `MachineConfig` in place for the life of the pool,
and re-check after an OpenShift upgrade rebases the base image.

**Scope the pool deliberately.** Only nodes that mount TLS volumes need the layer. On a
cluster with separate control-plane and worker pools, layering `worker` alone is smaller
blast radius and a shorter rollout than layering both.

**Entitlement certificates expire.** They are typically valid for a year. A build that
previously worked and now cannot resolve `ktls-utils` is usually an expired certificate
rather than a repository change.

**Never commit credentials into the image.** The entitlement certificate is a
subscription credential. The same-layer deletion above is the minimum; verifying the
built image before pushing is the check that catches a mistake.

---

## Next Steps

- Add `xprtsec=tls` to a test storage class and validate one volume before rolling the
  option out broadly. See the
  [OpenShift NFS Quickstart](../nfs/QUICKSTART.md).
- Confirm the array side separately. The client is only half the requirement; the array
  has its own minimum Purity version for NFS over TLS.
- Record the layered image build in whatever process handles your OpenShift upgrades, so
  the layer is rebuilt rather than silently lost at the next minor upgrade.

---

## Related Articles

- [OpenShift NFS Quickstart](../nfs/QUICKSTART.md) — the NFS provisioning that
  `xprtsec=tls` applies to
- [Kubernetes NFS Quickstart](../../kubernetes/nfs/QUICKSTART.md) — the same TLS option
  on nodes where `ktls-utils` installs from a package manager
- [NFS on RHEL Quickstart](../../rhel/nfs/QUICKSTART.md) — host-level NFS mounts and
  mount options
- [Red Hat: Mounting NFS shares](https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/managing_file_systems/mounting-nfs-shares_managing-file-systems)
- [OpenShift: Machine configuration](https://docs.redhat.com/en/documentation/openshift_container_platform/4.19/html/machine_configuration/machine-configs-configure)
- [tlshd(8) manual page](https://manpages.opensuse.org/Tumbleweed/ktls-utils/tlshd.8.en.html)
