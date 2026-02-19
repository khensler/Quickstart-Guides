Create `/etc/multipath.conf`:

```bash
sudo tee /etc/multipath.conf > /dev/null <<'EOF'
defaults {
    find_multipaths      off
    polling_interval     10
    path_selector        "service-time 0"
    path_grouping_policy group_by_prio
    failback             immediate
    no_path_retry        0
}

devices {
    device {
        vendor           "PURE"
        product          "FlashArray"
        path_selector    "service-time 0"
        hardware_handler "1 alua"
        path_grouping_policy group_by_prio
        prio             alua
        failback         immediate
        path_checker     tur
        fast_io_fail_tmo 10
        dev_loss_tmo     60
        no_path_retry    0
    }
}
EOF

# Restart multipathd to apply configuration
sudo systemctl restart multipathd

# Verify multipath devices
sudo multipath -ll
```

> **Why `find_multipaths off`?** This ensures ALL paths to storage devices are claimed by multipath immediately, rather than waiting to detect multiple paths. See [iSCSI Best Practices](./BEST-PRACTICES.md#multipath-configuration) for detailed explanation.

