---
layout: default
title: Fibre Channel on Debian/Ubuntu - Best Practices Guide
---

# Fibre Channel on Debian/Ubuntu - Best Practices Guide

Comprehensive best practices for deploying Fibre Channel storage on Debian/Ubuntu systems in production environments.

---

{% include bestpractices/disclaimer-debian.md %}

---

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Debian/Ubuntu-Specific Considerations](#debianubuntu-specific-considerations)
- [Fabric & Zoning Guidance](#fabric--zoning-guidance)
- [AppArmor Configuration](#apparmor-configuration)
- [FC Architecture](#fc-architecture)
- [Multipath Configuration](#multipath-configuration)
- [Performance Tuning](#performance-tuning)
- [High Availability](#high-availability)
- [Monitoring & Maintenance](#monitoring--maintenance)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Deployment Topology

```mermaid
flowchart TB
    subgraph "Debian/Ubuntu Hosts"
        HOST1[Linux Host 1<br/>2x FC HBA Ports]
        HOST2[Linux Host 2<br/>2x FC HBA Ports]
        HOST3[Linux Host 3<br/>2x FC HBA Ports]
    end

    subgraph "FC Fabric"
        SWA[FC Switch — Fabric A<br/>16/32 Gbps]
        SWB[FC Switch — Fabric B<br/>16/32 Gbps]
    end

    subgraph "FlashArray"
        CTRL1[Controller 1<br/>FC Ports]
        CTRL2[Controller 2<br/>FC Ports]
        LUN[(Volumes)]
    end

    HOST1 ---|HBA Port 0| SWA
    HOST1 ---|HBA Port 1| SWB
    HOST2 ---|HBA Port 0| SWA
    HOST2 ---|HBA Port 1| SWB
    HOST3 ---|HBA Port 0| SWA
    HOST3 ---|HBA Port 1| SWB

    SWA --- CTRL1
    SWA --- CTRL2
    SWB --- CTRL1
    SWB --- CTRL2

    CTRL1 --- LUN
    CTRL2 --- LUN

    style LUN fill:#5d6d7e,stroke:#333,stroke-width:2px,color:#fff
    style SWA fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
    style SWB fill:#1a5490,stroke:#333,stroke-width:2px,color:#fff
```

**Key points for Debian/Ubuntu:**
- Dual-fabric topology (Fabric A and Fabric B) required for redundancy
- Each HBA port connects to a separate fabric — never both ports to the same switch
- Minimum 2×2 topology (2 HBA ports × 2 array controller ports = 4 paths)
- No IP or network configuration required on the host for FC storage traffic

---

## Debian/Ubuntu-Specific Considerations

### Kernel and Driver Notes

Debian and Ubuntu ship the `lpfc` and `qla2xxx` HBA drivers in the standard kernel. No out-of-tree packages are typically required.

**Check running kernel:**
```bash
uname -r
```

**Verify FC modules are loaded:**
```bash
lsmod | grep -E "lpfc|qla2xxx|bnx2fc"

# Load manually if not autoloaded after HBA is installed
sudo modprobe lpfc    # Broadcom/Emulex
sudo modprobe qla2xxx # Marvell/QLogic
```

**Make module load persistent:**
```bash
echo "lpfc" | sudo tee -a /etc/modules
# or
echo "qla2xxx" | sudo tee -a /etc/modules
```

### Package Management

**Essential packages:**
```bash
sudo apt update
sudo apt install -y \
    multipath-tools \
    lvm2 \
    sg3-utils \
    sysfsutils \
    scsitools

# Performance monitoring tools
sudo apt install -y \
    sysstat \
    iotop \
    htop

# Optional: rescan-scsi-bus
sudo apt install -y scsitools
```

**Verify installation:**
```bash
multipath -ll
systemctl status multipathd
```

---

## Fabric & Zoning Guidance

### Single-Initiator Zoning (Required)

Each host WWPN must be in its own zone paired with the array's target ports. Never put multiple host initiators in the same zone.

**Correct zoning pattern:**
```
Zone: host1-hba0-to-array
  Members: host1-wwpn-hba0, array-ct0-port0, array-ct0-port1, array-ct1-port0, array-ct1-port1

Zone: host1-hba1-to-array
  Members: host1-wwpn-hba1, array-ct0-port2, array-ct0-port3, array-ct1-port2, array-ct1-port3
```

**Why single-initiator zoning:**
- Prevents unauthorized host-to-host communication over the fabric
- Reduces the blast radius of fabric events — a LIP on one initiator does not affect others
- Matches best practice guidance from Pure Storage, Broadcom, and Marvell/QLogic

### Discovering WWPNs for Zoning

```bash
# Collect WWPNs from host — provide to SAN admin for zoning
cat /sys/class/fc_host/host*/port_name
```

---

## AppArmor Configuration

### Understanding AppArmor with FC Storage

AppArmor does not directly govern FC transport, but it may restrict access to multipath device nodes and LVM operations depending on the active profiles.

**Check AppArmor status:**
```bash
sudo aa-status
```

### AppArmor and Multipath

If AppArmor blocks multipath operations, check for denials:

```bash
sudo dmesg | grep -i apparmor | grep -i DENIED | tail -20
sudo journalctl -k | grep -i "apparmor.*DENIED" | tail -20
```

**Add an exception if needed:**
```bash
# Edit the profile or create a local override
sudo aa-complain /usr/sbin/multipathd
# Test and then re-enable enforce mode after verifying behavior
sudo aa-enforce /usr/sbin/multipathd
```

**Best practice:** In Ubuntu, the `multipathd` AppArmor profile ships with the `multipath-tools` package and is generally compatible with standard FC storage configurations. Only intervene if you observe active DENIED log entries.

---

## FC Architecture

### How FC Storage Appears in Linux

```
FC Fabric
  └── HBA Driver (lpfc / qla2xxx)
        └── SCSI Mid-Layer
              └── SCSI Disk (sdX — one per path)
                    └── dm-multipath
                          └── /dev/mapper/mpathX  ← application uses this
                                └── LVM (optional)
```

**Key points:**
- Each FC path presents as an independent `sdX` device
- dm-multipath aggregates all `sdX` devices for the same LUN into `/dev/mapper/mpathX`
- Always target `/dev/mapper/` devices, never raw `sdX` paths
- ALUA identifies preferred (active/optimized) vs. available (active/non-optimized) paths

---

## Multipath Configuration

### Enable and Configure Multipath

```bash
sudo systemctl enable --now multipathd
```

### Debian/Ubuntu-Optimized multipath.conf

```bash
sudo tee /etc/multipath.conf > /dev/null <<'EOF'
defaults {
    find_multipaths         no
    polling_interval        10
    path_selector           "service-time 0"
    path_grouping_policy    group_by_prio
    failback                immediate
    no_path_retry           0
}

blacklist {
    devnode "^(ram|raw|loop|fd|md|dm-|sr|scd|st|nvme)[0-9]*"
    devnode "^sd[a]$"
    devnode "^vd[a-z]"
}

# Add device-specific settings for your storage array
# Consult your storage vendor documentation for recommended values
#devices {
#    device {
#        vendor               "VENDOR"
#        product              "PRODUCT"
#        path_selector        "service-time 0"
#        hardware_handler     "1 alua"
#        path_grouping_policy group_by_prio
#        prio                 alua
#        failback             immediate
#        path_checker         tur
#        fast_io_fail_tmo     5
#        dev_loss_tmo         60
#        no_path_retry        0
#    }
#}
EOF

sudo systemctl restart multipathd
sudo multipath -ll
```

### Verify Multipath

```bash
# Show multipath topology — expect 4 paths (2 HBA ports × 2 array controllers)
sudo multipath -ll

# Check for errors
sudo journalctl -u multipathd -n 50
```

---

## Performance Tuning

### HBA Queue Depth

**Tune Emulex (lpfc) queue depth:**
```bash
sudo tee /etc/modprobe.d/lpfc.conf > /dev/null <<'EOF'
options lpfc lpfc_lun_queue_depth=64
EOF

sudo update-initramfs -u
sudo reboot
```

**Tune QLogic (qla2xxx) queue depth:**
```bash
sudo tee /etc/modprobe.d/qla2xxx.conf > /dev/null <<'EOF'
options qla2xxx ql2xmaxqdepth=64
EOF

sudo update-initramfs -u
sudo reboot
```

### Device-Level Queue Depth

```bash
# Persistent udev rule — set queue depth for Pure FlashArray devices
sudo tee /etc/udev/rules.d/99-pure-fc-queue-depth.rules > /dev/null <<'EOF'
ACTION=="add|change", SUBSYSTEM=="block", ATTRS{model}=="FlashArray*", ATTR{device/queue_depth}="64"
EOF

sudo udevadm control --reload-rules
sudo udevadm trigger
```

> **⚠️ Note:** These queue depth values are starting points for testing. Validate with performance monitoring (`iostat -x 1`, vendor telemetry) before deploying to production.

---

## High Availability

### Failover Timers

| Parameter | Recommended | Effect |
|-----------|-------------|--------|
| `fast_io_fail_tmo` | 5 seconds | Time to fail I/O after fabric reports link down |
| `dev_loss_tmo` | 60 seconds | Time before device is removed after persistent failure |
| `failback` | `immediate` | Restore preferred paths as soon as they come back online |

### Testing Path Failover

```bash
# Identify path devices
sudo multipath -ll

# Disable one path (replace sdb with actual device)
echo offline | sudo tee /sys/block/sdb/device/state

# Verify multipath reroutes
sudo multipath -ll

# Re-enable the path
echo running | sudo tee /sys/block/sdb/device/state
```

---

## Monitoring & Maintenance

### Check HBA Link State

```bash
cat /sys/class/fc_host/host*/port_state
cat /sys/class/fc_host/host*/link_failure_count
cat /sys/class/fc_host/host*/speed
```

### Monitor Multipath

```bash
sudo multipath -ll
sudo multipathd -k"show paths"
sudo journalctl -u multipathd -f
```

---

## Security

### FC Security Model

Fibre Channel security is implemented at the fabric level — there is no host-level equivalent to iSCSI CHAP. Security controls:

1. **Fabric zoning** — primary access control; only zoned initiators can communicate with target ports
2. **LUN masking / host registration** — the storage array independently enforces access based on WWPN registration and host group membership
3. **Hard zoning** — enforce at the switch port level for strongest isolation

**No host-level firewall is required for FC storage traffic.** FC does not traverse IP networks.

---

## Troubleshooting

### LUNs Not Appearing After Rescan

```bash
# 1. Verify HBA ports are online
cat /sys/class/fc_host/host*/port_state

# 2. Check HBA link errors
cat /sys/class/fc_host/host*/link_failure_count

# 3. Force rescan
sudo rescan-scsi-bus.sh -a -r
# or
for host in /sys/class/scsi_host/host*; do echo "- - -" | sudo tee "$host/scan"; done

# 4. Check device visibility
lsscsi
sudo multipath -ll
```

**If still not visible:** Confirm with SAN administrator that zoning is in place and the volume is connected to the correct host group on the FlashArray.

### Fewer Than Expected Paths

```bash
for h in /sys/class/fc_host/host*; do
    echo "$h: $(cat $h/port_state) — WWPN: $(cat $h/port_name)"
done
```

**Common causes:** One HBA port not cabled, zone missing for one HBA port, volume not connected on array for one controller.

### Path Flapping

```bash
cat /sys/class/fc_host/host*/link_failure_count
cat /sys/class/fc_host/host*/loss_of_signal_count
sudo dmesg | grep -i "fc\|scsi" | tail -50
```

**Common causes:** Faulty SFP/cable, switch port errors, HBA firmware issue.
