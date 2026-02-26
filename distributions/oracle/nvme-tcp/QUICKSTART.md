---
layout: default
title: NVMe-TCP on Oracle Linux - Quick Start Guide
---

# NVMe-TCP on Oracle Linux - Quick Start Guide

This guide provides a streamlined path to configure NVMe-TCP storage on Oracle Linux.

> **📘 For detailed explanations, alternative configurations, and troubleshooting:** See [NVMe-TCP Best Practices](./BEST-PRACTICES.md)

---

{% include quickstart/disclaimer.md %}

---

## Prerequisites

- Oracle Linux 9.x with UEK 8 (6.12+) or Oracle Linux 8.x with UEK R7 (5.15+)
- NVMe-TCP storage array with portal IPs and subsystem NQN
- Dedicated storage network interfaces
- Root or sudo access

> **Note:** This guide was validated on Oracle Linux 9.7 with UEK 8 (kernel 6.12). The same configuration applies to Oracle Linux 10 which also uses UEK 8.

{% include quickstart/glossary-link-nvme.md %}

{% include quickstart/arp-warning.md %}

## Step 1: Install Packages

```bash
sudo dnf install -y nvme-cli
sudo modprobe nvme-tcp
echo "nvme-tcp" | sudo tee /etc/modules-load.d/nvme-tcp.conf
```

## Step 2: Configure Network Interfaces

{% include quickstart/network-rhel.md %}

## Step 3: Configure Firewall

{% include quickstart/firewall-rhel.md %}

> **Alternative:** For port filtering options, see [Best Practices - Firewall Configuration](./BEST-PRACTICES.md#firewall-configuration).

## Step 4: Generate Host NQN

{% include quickstart/nvme-generate-hostnqn.md %}

## Step 5: Connect to NVMe Subsystems

{% include quickstart/nvme-connect-storage.md %}

## Step 6: Configure IO Policy

{% include quickstart/nvme-io-policy.md %}

## Step 7: Configure Persistent Connections

> **Important:** On Oracle Linux (and RHEL-based systems), the standard `nvmf-autoconnect.service` does **not** work for NVMe-TCP connections. A custom systemd service is required.

Create a systemd service to connect NVMe-TCP storage at boot:

```bash
# Create the systemd service file
sudo tee /etc/systemd/system/nvme-tcp-connect.service > /dev/null <<EOF
[Unit]
Description=Connect NVMe-TCP subsystems at boot
After=network-online.target
Wants=network-online.target
After=modprobe@nvme_fabrics.service

[Service]
Type=oneshot
ExecStart=/usr/sbin/nvme connect-all -t tcp -a <PORTAL_IP> -s 4420 --ctrl-loss-tmo=-1 --reconnect-delay=5
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable --now nvme-tcp-connect.service

# Verify the service status
sudo systemctl status nvme-tcp-connect.service
```

Replace `<PORTAL_IP>` with one of your NVMe-TCP portal IP addresses. The `connect-all` command will discover and connect to all available subsystems through that portal.

## Step 8: Create LVM Storage

{% include quickstart/nvme-lvm-storage.md %}

```bash
# Format and mount (Oracle Linux: XFS recommended)
sudo mkfs.xfs /dev/nvme-storage/data
sudo mkdir -p /mnt/nvme-storage
sudo mount /dev/nvme-storage/data /mnt/nvme-storage

# Add to fstab
echo '/dev/nvme-storage/data /mnt/nvme-storage xfs defaults,_netdev 0 0' | sudo tee -a /etc/fstab
```

## Step 9: Verify

{% include quickstart/nvme-verify.md %}

---

{% include quickstart/nvme-quick-reference.md %}

---

## Next Steps

For production deployments, see [NVMe-TCP Best Practices](./BEST-PRACTICES.md) for:
- Network design and VLAN configuration
- Performance tuning
- Security best practices (SELinux, firewall options)
- Monitoring and troubleshooting
- High availability considerations
- UEK vs RHCK kernel selection
- Ksplice zero-downtime updates

**Additional Resources:**
- [Common Network Concepts]({{ site.baseurl }}/common/network-concepts.html)
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html)
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html)
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html)

