Create `/etc/multipath.conf`:

```bash
sudo tee /etc/multipath.conf > /dev/null <<'EOF'
defaults {
    find_multipaths      no
    polling_interval     10
    path_selector        "service-time 0"
    path_grouping_policy group_by_prio
    failback             immediate
    no_path_retry        0
}

# Blacklist local devices and NVMe to prevent dm-multipath management
# NVMe uses native multipath (nvme_core multipath=Y), not dm-multipath
blacklist {
    # Local boot devices (adjust patterns for your environment)
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st)[0-9]*"
    devnode "^sd[a]$"    # Adjust if boot device differs

    # All NVMe devices - use native NVMe multipath instead
    devnode "^nvme"

    # Virtual devices
    devnode "^vd[a-z]"
}

# Add device-specific settings for your storage array
# Default configurations for many storage arrays are included in the multipath package
# Example for a storage array supporting ALUA:
#devices {
#    device {
#        vendor           "VENDOR"
#        product          "PRODUCT"
#        path_selector    "service-time 0"
#        hardware_handler "1 alua"
#        path_grouping_policy group_by_prio
#        prio             alua
#        failback         immediate
#        path_checker     tur
#        fast_io_fail_tmo 5
#        dev_loss_tmo     60
#        no_path_retry    0
#    }
#}
EOF

# Restart multipathd to apply configuration
sudo systemctl restart multipathd

# Verify multipath devices (should only show FC/SAN devices)
sudo multipath -ll
```

> **Why `find_multipaths no`?** This ensures ALL paths to FC storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. See [Best Practices - Multipath Configuration](./BEST-PRACTICES.md#multipath-configuration) for a detailed explanation.

> **Why `fast_io_fail_tmo 5` and `dev_loss_tmo 60`?** FC path failures must be detected quickly to enable failover. `fast_io_fail_tmo` is the number of seconds to wait before failing I/O when the fabric reports a link down; `dev_loss_tmo` is how long to wait before removing the device entirely. These values balance fast failover with transient link-bounce recovery.

