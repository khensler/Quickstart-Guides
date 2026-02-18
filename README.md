# Quickstart Guides

A collection of quick start guides for various technologies and configurations.

## Guides

### Distribution-Specific Guides

**Proxmox VE:**

- [NVMe-TCP Setup Guide](Proxmox/nvme-tcp/QUICKSTART.md) - Configure NVMe over TCP for Proxmox VE
- [NVMe-TCP Best Practices](Proxmox/nvme-tcp/BEST-PRACTICES.md) - Production deployment best practices with architectural diagrams
- [iSCSI Setup Guide](Proxmox/iscsi/QUICKSTART.md) - Configure iSCSI for Proxmox VE
- [VMware to Proxmox Migration Guide for Pure vVols](Proxmox/migration/VMware-Proxmox-Manual-Migration.md) - Manual migration of VMs from VMware to Proxmox using Pure vVols

**RHEL/Rocky/AlmaLinux:**
- [NVMe-TCP Quick Start](distributions/rhel/nvme-tcp/QUICKSTART.md) - Quick start guide for RHEL-based distributions
- [NVMe-TCP Best Practices](distributions/rhel/nvme-tcp/BEST-PRACTICES.md) - Best practices with SELinux, firewalld, and tuned profiles
- [iSCSI Quick Start](distributions/rhel/iscsi/QUICKSTART.md) - iSCSI configuration for RHEL-based distributions
- [iSCSI Best Practices](distributions/rhel/iscsi/BEST-PRACTICES.md) - iSCSI best practices for RHEL-based distributions

**Debian/Ubuntu:**
- [NVMe-TCP Quick Start](distributions/debian/nvme-tcp/QUICKSTART.md) - Quick start guide for Debian and Ubuntu
- [NVMe-TCP Best Practices](distributions/debian/nvme-tcp/BEST-PRACTICES.md) - Best practices with AppArmor, UFW, and netplan
- [iSCSI Quick Start](distributions/debian/iscsi/QUICKSTART.md) - iSCSI configuration for Debian and Ubuntu
- [iSCSI Best Practices](distributions/debian/iscsi/BEST-PRACTICES.md) - iSCSI best practices for Debian and Ubuntu

**SUSE/openSUSE:**
- [NVMe-TCP Quick Start](distributions/suse/nvme-tcp/QUICKSTART.md) - Quick start guide for SUSE Linux Enterprise and openSUSE
- [NVMe-TCP Best Practices](distributions/suse/nvme-tcp/BEST-PRACTICES.md) - Best practices with YaST, wicked, and AppArmor
- [iSCSI Quick Start](distributions/suse/iscsi/QUICKSTART.md) - iSCSI configuration for SUSE Linux Enterprise and openSUSE
- [iSCSI Best Practices](distributions/suse/iscsi/BEST-PRACTICES.md) - iSCSI best practices for SUSE and openSUSE

**Oracle Linux:**
- [NVMe-TCP Quick Start](distributions/oracle/nvme-tcp/QUICKSTART.md) - Quick start guide for Oracle Linux with UEK
- [NVMe-TCP Best Practices](distributions/oracle/nvme-tcp/BEST-PRACTICES.md) - Best practices with UEK tuning and Ksplice
- [iSCSI Quick Start](distributions/oracle/iscsi/QUICKSTART.md) - iSCSI configuration for Oracle Linux with UEK
- [iSCSI Best Practices](distributions/oracle/iscsi/BEST-PRACTICES.md) - iSCSI best practices for Oracle Linux with UEK

### Common Reference Documentation

- **[Storage Terminology Glossary](common/includes/glossary.md)** - Definitions for iSCSI, NVMe-TCP, and storage terms (IQN, NQN, Portal, LUN, Namespace, etc.)
- [Network Concepts](common/includes/network-concepts.md) - Network architecture, topology, MTU, and performance tuning
- [Multipath Concepts](common/includes/multipath-concepts.md) - Multipath configuration, path selection, and monitoring
- [Performance Tuning](common/includes/performance-tuning.md) - CPU/IRQ tuning, kernel parameters, I/O scheduler
- [Security Best Practices](common/includes/security-best-practices.md) - Network security, authentication, encryption
- [Troubleshooting Common Issues](common/includes/troubleshooting-common.md) - Connection, performance, multipath, boot issues
- [Monitoring & Maintenance](common/includes/monitoring-maintenance.md) - Monitoring procedures and maintenance tasks
- [iSCSI Architecture](common/includes/iscsi-architecture.md) - iSCSI architecture, concepts, and terminology
- [iSCSI Multipath Configuration](common/includes/iscsi-multipath-config.md) - iSCSI multipath configuration and APD handling
- [iSCSI Performance Tuning](common/includes/iscsi-performance-tuning.md) - iSCSI-specific performance optimization
