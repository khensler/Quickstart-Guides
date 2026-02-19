---
layout: default
title: Home
nav_order: 1
---

# Pure Storage Linux Configuration Guides

Best practices for configuring NVMe-TCP and iSCSI storage on Linux distributions with Pure Storage FlashArray.

> **⚠️ Disclaimer:** This content is specific to Pure Storage configurations and for reference only. Always consult official vendor documentation for your distribution and storage array. Test thoroughly in a lab environment before production use.

---

## Quick Start

Choose your distribution and protocol to get started:

| Distribution | NVMe-TCP | iSCSI |
|:-------------|:---------|:------|
| **RHEL/Rocky/Alma** | [Quickstart](distributions/rhel/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/rhel/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/rhel/iscsi/QUICKSTART.md) \| [Best Practices](distributions/rhel/iscsi/BEST-PRACTICES.md) |
| **Debian/Ubuntu** | [Quickstart](distributions/debian/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/debian/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/debian/iscsi/QUICKSTART.md) \| [Best Practices](distributions/debian/iscsi/BEST-PRACTICES.md) |
| **SUSE/openSUSE** | [Quickstart](distributions/suse/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/suse/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/suse/iscsi/QUICKSTART.md) \| [Best Practices](distributions/suse/iscsi/BEST-PRACTICES.md) |
| **Oracle Linux** | [Quickstart](distributions/oracle/nvme-tcp/QUICKSTART.md) \| [Best Practices](distributions/oracle/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](distributions/oracle/iscsi/QUICKSTART.md) \| [Best Practices](distributions/oracle/iscsi/BEST-PRACTICES.md) |
| **Proxmox VE** | [Quickstart](Proxmox/nvme-tcp/QUICKSTART.md) \| [Best Practices](Proxmox/nvme-tcp/BEST-PRACTICES.md) | [Quickstart](Proxmox/iscsi/QUICKSTART.md) \| [Best Practices](Proxmox/iscsi/BEST-PRACTICES.md) |

---

## Common Resources

These reference documents are included inline throughout the Best Practices guides.

- [Storage Terminology Glossary](_includes/glossary.md) - Key terms for iSCSI and NVMe-TCP
- [Network Architecture Concepts](_includes/network-concepts.md) - Network design and ARP configuration
- [Multipath Concepts](_includes/multipath-concepts.md) - Path management and failover
- [Security Best Practices](_includes/security-best-practices.md) - Firewall and access control
- [Troubleshooting Guide](_includes/troubleshooting-common.md) - Common issues and solutions

---

## Document Types

**QUICKSTART Guides** - Short, opinionated guides with a single recommended configuration path. Get up and running quickly.

**BEST-PRACTICES Guides** - Comprehensive documentation with multiple options, detailed explanations, diagrams, and troubleshooting information.

