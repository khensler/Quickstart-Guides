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

If pods set `fsGroup` and fail with `permission denied` or `lchown failed`, set `pure_export_rules: "*(rw,no_root_squash)"` — scoped to the node networks rather than `*` wherever possible.
