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
#        fast_io_fail_tmo 10
#        dev_loss_tmo     60
#        no_path_retry    0
#    }
#}
EOF

# Restart multipathd to apply configuration
sudo systemctl restart multipathd

# Verify multipath devices (should only show iSCSI devices)
sudo multipath -ll
```

> **Why blacklist local and NVMe devices?**
> - **Local devices**: Prevents dm-multipath from managing boot drives and local storage
> - **NVMe devices**: NVMe uses native kernel multipath (`nvme_core multipath=Y`), not dm-multipath. Managing NVMe with dm-multipath causes conflicts and performance issues.

> **Why `find_multipaths off`?** This ensures ALL paths to iSCSI storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. See [iSCSI Best Practices](./BEST-PRACTICES.md#multipath-configuration) for detailed explanation.

