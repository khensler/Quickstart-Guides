---
layout: default
title: Quickstart Guides
---

# Quickstart Guides

A collection of quick start guides for various technologies and configurations.

## Guides

### Getting Started

- [Choosing a Storage Protocol](common/choosing-a-protocol.md) - Compare NVMe-TCP, iSCSI, and NFS to select the right protocol for your workload

### Distribution-Specific Guides

**Proxmox VE:**

- [NVMe-TCP Setup Guide](distributions/proxmox/nvme-tcp/QUICKSTART.md) - Configure NVMe over TCP for Proxmox VE
- [NVMe-TCP Best Practices](distributions/proxmox/nvme-tcp/BEST-PRACTICES.md) - Production deployment best practices with architectural diagrams
- [iSCSI Setup Guide](distributions/proxmox/iscsi/QUICKSTART.md) - Configure iSCSI for Proxmox VE
- [iSCSI Best Practices](distributions/proxmox/iscsi/BEST-PRACTICES.md) - Production deployment best practices for iSCSI on Proxmox VE
- [NFS Setup Guide](distributions/proxmox/nfs/QUICKSTART.md) - Configure NFS storage for Proxmox VE
- [NFS Best Practices](distributions/proxmox/nfs/BEST-PRACTICES.md) - Production deployment best practices for NFS on Proxmox VE
- [VMware to Proxmox Migration Guide (Pure Storage vVols)](distributions/proxmox/migration/VMware-Proxmox-Manual-Migration.md) - Manual migration of VMs from VMware to Proxmox using Pure Storage vVols (vendor-specific guide)

**RHEL/Rocky/AlmaLinux:**
- [NVMe-TCP Quick Start](distributions/rhel/nvme-tcp/QUICKSTART.md) - Quick start guide for RHEL-based distributions
- [NVMe-TCP Best Practices](distributions/rhel/nvme-tcp/BEST-PRACTICES.md) - Best practices with SELinux, firewalld, and tuned profiles
- [iSCSI Quick Start](distributions/rhel/iscsi/QUICKSTART.md) - iSCSI configuration for RHEL-based distributions
- [iSCSI Best Practices](distributions/rhel/iscsi/BEST-PRACTICES.md) - iSCSI best practices for RHEL-based distributions
- [NFS Quick Start](distributions/rhel/nfs/QUICKSTART.md) - NFS configuration for RHEL-based distributions
- [NFS Best Practices](distributions/rhel/nfs/BEST-PRACTICES.md) - NFS best practices with nconnect and SELinux

**Debian/Ubuntu:**
- [NVMe-TCP Quick Start](distributions/debian/nvme-tcp/QUICKSTART.md) - Quick start guide for Debian and Ubuntu
- [NVMe-TCP Best Practices](distributions/debian/nvme-tcp/BEST-PRACTICES.md) - Best practices with AppArmor, UFW, and netplan
- [iSCSI Quick Start](distributions/debian/iscsi/QUICKSTART.md) - iSCSI configuration for Debian and Ubuntu
- [iSCSI Best Practices](distributions/debian/iscsi/BEST-PRACTICES.md) - iSCSI best practices for Debian and Ubuntu
- [NFS Quick Start](distributions/debian/nfs/QUICKSTART.md) - NFS configuration for Debian and Ubuntu
- [NFS Best Practices](distributions/debian/nfs/BEST-PRACTICES.md) - NFS best practices with nconnect and AppArmor

**SUSE/openSUSE:**
- [NVMe-TCP Quick Start](distributions/suse/nvme-tcp/QUICKSTART.md) - Quick start guide for SUSE Linux Enterprise and openSUSE
- [NVMe-TCP Best Practices](distributions/suse/nvme-tcp/BEST-PRACTICES.md) - Best practices with YaST, wicked, and AppArmor
- [iSCSI Quick Start](distributions/suse/iscsi/QUICKSTART.md) - iSCSI configuration for SUSE Linux Enterprise and openSUSE
- [iSCSI Best Practices](distributions/suse/iscsi/BEST-PRACTICES.md) - iSCSI best practices for SUSE and openSUSE
- [NFS Quick Start](distributions/suse/nfs/QUICKSTART.md) - NFS configuration for SUSE and openSUSE
- [NFS Best Practices](distributions/suse/nfs/BEST-PRACTICES.md) - NFS best practices with nconnect and wicked

**Oracle Linux:**
- [NVMe-TCP Quick Start](distributions/oracle/nvme-tcp/QUICKSTART.md) - Quick start guide for Oracle Linux with UEK
- [NVMe-TCP Best Practices](distributions/oracle/nvme-tcp/BEST-PRACTICES.md) - Best practices with UEK tuning and Ksplice
- [iSCSI Quick Start](distributions/oracle/iscsi/QUICKSTART.md) - iSCSI configuration for Oracle Linux with UEK
- [iSCSI Best Practices](distributions/oracle/iscsi/BEST-PRACTICES.md) - iSCSI best practices for Oracle Linux with UEK
- [NFS Quick Start](distributions/oracle/nfs/QUICKSTART.md) - NFS configuration for Oracle Linux
- [NFS Best Practices](distributions/oracle/nfs/BEST-PRACTICES.md) - NFS best practices with UEK and nconnect

**XCP-ng:**
- [NVMe-TCP Quick Start](distributions/xcpng/nvme-tcp/QUICKSTART.md) - NVMe-TCP configuration for XCP-ng (experimental)
- [NVMe-TCP Best Practices](distributions/xcpng/nvme-tcp/BEST-PRACTICES.md) - Production best practices for NVMe-TCP on XCP-ng
- [iSCSI Quick Start (CLI)](distributions/xcpng/iscsi/QUICKSTART.md) - iSCSI configuration via xe CLI
- [iSCSI Quick Start (GUI)](distributions/xcpng/iscsi/GUI-QUICKSTART.md) - iSCSI setup with Xen Orchestra and multipathing
- [iSCSI Best Practices](distributions/xcpng/iscsi/BEST-PRACTICES.md) - Production best practices for iSCSI on XCP-ng
- [NFS Quick Start (GUI)](distributions/xcpng/nfs/QUICKSTART.md) - NFS storage setup with Xen Orchestra

### Cloud & Hybrid Infrastructure

**AWS Outposts:**
- [Everpure FlashArray for AWS Outposts](distributions/aws-outposts/QUICKSTART.md) - Connect EC2 instances on AWS Outposts to FlashArray for data and boot volumes (NVMe-TCP and iSCSI)

### Common Reference Documentation

- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html) - Definitions for iSCSI, NVMe-TCP, and storage terms (IQN, NQN, Portal, LUN, Namespace, etc.)
- [Network Concepts]({{ site.baseurl }}/common/network-concepts.html) - Network architecture, topology, MTU, and performance tuning
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html) - Multipath configuration, path selection, and monitoring
- [Performance Tuning]({{ site.baseurl }}/common/performance-tuning.html) - CPU/IRQ tuning, kernel parameters, I/O scheduler
- [Security Best Practices]({{ site.baseurl }}/common/security-best-practices.html) - Network security, authentication, encryption
- [Troubleshooting Common Issues]({{ site.baseurl }}/common/troubleshooting-common.html) - Connection, performance, multipath, boot issues
- [Monitoring & Maintenance]({{ site.baseurl }}/common/monitoring-maintenance.html) - Monitoring procedures and maintenance tasks
- [iSCSI Architecture]({{ site.baseurl }}/common/iscsi-architecture.html) - iSCSI architecture, concepts, and terminology
- [iSCSI Multipath Configuration]({{ site.baseurl }}/common/iscsi-multipath-config.html) - iSCSI multipath configuration and APD handling
- [iSCSI Performance Tuning]({{ site.baseurl }}/common/iscsi-performance-tuning.html) - iSCSI-specific performance optimization
