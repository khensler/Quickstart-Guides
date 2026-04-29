# HPE VME Documentation — Changelog

## 2026-04-29 — Fabricated Content Audit & Cleanup

### Problem
Best practices guides contained significant fabricated content — bonding configs, sysctl tuning, performance numbers, Linux NFS server commands, monitoring scripts, CHAP references, and architectural details that were not verified in the lab or sourced from HPE documentation.

### Root Cause
Quickstart guides were written from lab work and screenshots (accurate). Best practices guides were padded with generic content to appear comprehensive.

### Changes — iSCSI BEST-PRACTICES.md (753 → 294 lines)
- **Removed** GFS2 DLM/Corosync architecture diagram (internal detail not verified)
- **Removed** manual GFS2 commands (`gfs2_tool df` — deprecated, never tested)
- **Removed** CHAP authentication reference (not tested in lab)
- **Removed** HA section with unverified Corosync/DLM/fencing/journal replay claims
- **Removed** "Path failover tested" from checklist (not tested)
- **Removed** "Cluster fencing configured" from checklist (not tested)
- **Removed** duplicate HPE VME Manager Configuration section
- **Removed** Performance Tuning section (never existed — was removed in earlier pass)
- **Removed** second redundant network diagram
- **Added** source attribution note to Pure multipath.conf
- **Added** HPE docs link for GFS2 minimum 3-node quorum requirement
- **Fixed** Table of Contents to match actual sections
- **Fixed** made-up example IPs replaced with `<placeholder>` format
- **Simplified** GFS2 section to reference Quickstart for procedure details

### Changes — NFS BEST-PRACTICES.md (508 → 308 lines)
- **Removed** fabricated network diagram (bond0.2, eth1, VLAN 2, VLAN 100 — all made up)
- **Removed** `hpe-vm` console command section (not verified)
- **Removed** all netplan/bonding configurations (not tested for NFS)
- **Removed** LACP, balance-xor, active-backup bond mode recommendations
- **Removed** Performance Tuning section entirely:
  - Fabricated sysctl values (rmem_max, tcp_timestamps, etc.)
  - Fabricated NFS mount options
  - Fabricated performance expectations table (800+ MB/s, 2+ GB/s — made up)
- **Removed** monitoring script (untested)
- **Removed** `nfsstat -s` and `rpcinfo` server-side commands (not applicable to Pure)
- **Removed** `exportfs -v` troubleshooting (Linux NFS server command, not Pure FlashArray)
- **Removed** "NFS mount hangs" section with generic firewall port advice
- **Removed** "Firewall rules on NFS server" from security (not applicable to Pure)
- **Removed** "When to Use NFS" section (fabricated recommendations)
- **Removed** NFS Datastore Types list (fabricated)
- **Removed** HCI/Ceph storage layout table
- **Replaced** NFS Server Checklist with Pure FlashArray Export Checklist
- **Simplified** Network Configuration to HPE-documented 3-interface recommendation + MTU checklist
- **Simplified** Monitoring section to table of lab-verified commands
- **Fixed** Table of Contents to match actual sections

### Changes — iSCSI QUICKSTART.md
- **Fixed** made-up example IPs (192.168.x.x) replaced with `<placeholder>` format
- **Removed** Host OS prerequisite row
- **Removed** package install checks (open-iscsi, multipath-tools)

### Changes — NFS QUICKSTART.md
- **Fixed** NFSv4 screenshot replaced with verified NFSv3 screenshot
- **Removed** Host OS prerequisite row

### Guiding Principle
Nothing in these documents unless it comes from:
1. Lab-verified testing on our 3-node VME cluster with Pure FlashArray
2. Official HPE VME documentation (https://hpevm-docs.morpheusdata.com/)
3. Official Pure Storage documentation (https://support.purestorage.com)
