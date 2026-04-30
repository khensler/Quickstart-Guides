---
layout: home
title: Home
---

# Linux Storage Configuration Guides

Best practices for configuring NVMe-TCP and iSCSI storage on Linux distributions.

> **⚠️ Disclaimer:** This content is for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use.

---

## Quick Start

**Not sure which protocol to use?** See the [Choosing a Storage Protocol](common/choosing-a-protocol.md) guide.

Choose your distribution and protocol to get started:

| Distribution | NVMe-TCP | iSCSI | NFS |
|:-------------|:---------|:------|:----|
| **RHEL/Rocky/Alma** | [Quickstart](distributions/rhel/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/rhel/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/rhel/iscsi/QUICKSTART.md) \| [Best Practices](distributions/rhel/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/rhel/nfs/QUICKSTART.md) \| [Best Practices](distributions/rhel/nfs/BEST-PRACTICES.md) |
| **Debian/Ubuntu** | [Quickstart](distributions/debian/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/debian/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/debian/iscsi/QUICKSTART.md) \| [Best Practices](distributions/debian/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/debian/nfs/QUICKSTART.md) \| [Best Practices](distributions/debian/nfs/BEST-PRACTICES.md) |
| **SUSE/openSUSE** | [Quickstart](distributions/suse/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/suse/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/suse/iscsi/QUICKSTART.md) \| [Best Practices](distributions/suse/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/suse/nfs/QUICKSTART.md) \| [Best Practices](distributions/suse/nfs/BEST-PRACTICES.md) |
| **Oracle Linux** | [Quickstart](distributions/oracle/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/oracle/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/oracle/iscsi/QUICKSTART.md) \| [Best Practices](distributions/oracle/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/oracle/nfs/QUICKSTART.md) \| [Best Practices](distributions/oracle/nfs/BEST-PRACTICES.md) |
| **Proxmox VE** | [Quickstart](distributions/proxmox/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/proxmox/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/proxmox/iscsi/QUICKSTART.md) \| [Best Practices](distributions/proxmox/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/proxmox/nfs/QUICKSTART.md) \| [Best Practices](distributions/proxmox/nfs/BEST-PRACTICES.md) |
| **XCP-ng** | — | [Quickstart](distributions/xcpng/iscsi/QUICKSTART.md) \| [Best Practices](distributions/xcpng/iscsi/BEST-PRACTICES.md) \| [GUI Guide](distributions/xcpng/iscsi/GUI-QUICKSTART.md) | [Quickstart](distributions/xcpng/nfs/QUICKSTART.md) |
| **HPE VM Essentials** | — | [Quickstart](distributions/hpe-vme/iscsi/QUICKSTART.md) \| [Best Practices](distributions/hpe-vme/iscsi/BEST-PRACTICES.md) | [Quickstart](distributions/hpe-vme/nfs/QUICKSTART.md) \| [Best Practices](distributions/hpe-vme/nfs/BEST-PRACTICES.md) |

---

## Cloud & Hybrid Infrastructure

**AWS Outposts:**
- [Everpure FlashArray for AWS Outposts](distributions/aws-outposts/QUICKSTART.md) — Connect EC2 instances on AWS Outposts to FlashArray for data and boot volumes (NVMe-TCP and iSCSI)

---

## OpenStack Distributions

** Platform9 PCD:**
- [ Platform9 PCD Integration Guide](distributions/pcd/iscsi/GUIDE.md) — Integrate Pure Storage FlashArray with Platform9 PCD using iSCSI and DM-Multipath

---

## Common Resources

These reference documents are included inline throughout the Best Practices guides.

- [Choosing a Storage Protocol]({{ site.baseurl }}/common/choosing-a-protocol.html) - Compare NVMe-TCP, iSCSI, and NFS
- [Storage Terminology Glossary]({{ site.baseurl }}/common/glossary.html) - Key terms for iSCSI and NVMe-TCP
- [Network Architecture Concepts]({{ site.baseurl }}/common/network-concepts.html) - Network design and ARP configuration
- [Multipath Concepts]({{ site.baseurl }}/common/multipath-concepts.html) - Path management and failover
- [Security Best Practices]({{ site.baseurl }}/common/security-best-practices.html) - Firewall and access control
- [Troubleshooting Guide]({{ site.baseurl }}/common/troubleshooting-common.html) - Common issues and solutions

---

## Document Types

**QUICKSTART Guides** - Short, opinionated guides with a single recommended configuration path. Get up and running quickly.

**BEST-PRACTICES Guides** - Comprehensive documentation with multiple options, detailed explanations, diagrams, and troubleshooting information.

