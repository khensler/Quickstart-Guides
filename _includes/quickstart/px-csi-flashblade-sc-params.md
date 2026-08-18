| Parameter | Purpose |
|---|---|
| `pure_export_rules` | Sets the export rules directly, for example `*(rw)` or `*(rw,no_root_squash)`. Mutually exclusive with `pure_nfs_policy`. |
| `pure_nfs_policy` | Uses a pre-created FlashBlade NFS export policy instead of generated rules. |
| `pure_nfs_export_rules_access` | Sets the squash behavior: `root-squash`, `all-squash`, or `no-squash`. |
| `pure_nfs_endpoint` | Overrides the `NFSEndPoint` from `pure.json`. |
| `pure_nfs_server` | Names the NFS server, used with FlashBlade Realms. |
| `pure_fb_snapshot_directory_enabled` | Controls whether the snapshot directory is exposed in the file system. |
| `pure_fb_fast_remove_directory_enabled` | Enables fast directory removal. |
| `pure_fb_hard_limit_enabled` | Enforces the file system size as a hard limit rather than an advisory one. |
| `pure_fb_nfsv3_enabled` | Enables or disables NFSv3 on the provisioned file system. Set `"false"` for FlashBlade//EXA. |
| `pure_fb_nfsv4_1_enabled` | Enables or disables NFSv4.1 on the provisioned file system. Required `"true"` for FlashBlade//EXA. |
| `pure_fb_node_group` | Names the FlashBlade//EXA node group that governs capacity. |

**Two defaults worth knowing, because they differ from the FlashArray file backend.** Both
were observed on a provisioned volume using nothing but `backend` and `pure_export_rules`:

- **The size is enforced.** The provisioned file system came up with the hard limit
  **enabled**, so the PVC request is a real ceiling. This is the opposite of
  `pure_fa_file`, where the requested size is not enforced at all unless you attach a quota
  policy — do not carry an assumption either way between the two backends.
- **Both NFS versions are enabled.** The file system was created with NFSv3 *and* NFSv4.1
  on, which is why a standard FlashBlade class can mount at `nfsvers=4.1` without setting
  the version parameters explicitly. Confirm it on your own array rather than relying on
  it, since the export configuration is what ultimately decides.

If pods set `fsGroup` and fail with `permission denied` or `lchown failed`, set `pure_export_rules: "*(rw,no_root_squash)"` — scoped to the node networks rather than `*` wherever possible. With the default `*(rw)` the export enforces root squash, and files land owned by `nobody:nobody` regardless of the `fsGroup` you set.
