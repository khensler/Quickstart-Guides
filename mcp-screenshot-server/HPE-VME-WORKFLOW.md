# HPE Virtual Machine Essentials (VME) Documentation Workflow

Guide for using the MCP Screenshot Server to document HPE VME NFS and iSCSI configurations.

## Overview

This workflow is designed to help you create comprehensive documentation for HPE Virtual Machine Essentials (VME) servers, focusing on:

- **NFS Storage Configuration** - Network File System setup and management
- **iSCSI Storage Configuration** - iSCSI target and LUN configuration
- **HPE VME Management Interface** - Web-based administration console
- **Storage Integration** - Connecting VME to storage arrays

## HPE VME Interface Overview

HPE Virtual Machine Essentials provides a web-based management interface typically accessible at:
- `https://<vme-server>:8443` (default HTTPS port)
- `https://<vme-server>:443` (alternative)

Common pages to document:
- Dashboard
- Virtual Machines
- Storage Management
- Network Configuration
- iSCSI Configuration
- NFS Configuration
- Host Settings

## Documentation Workflow

### Phase 1: Initial Setup Documentation

**Capture the initial state of your HPE VME server:**

```
Capture screenshots of my HPE VME server at https://vme-server.lab:8443

1. Login page - save as "hpe-vme-01-login.png"
2. Dashboard after login - save as "hpe-vme-02-dashboard.png"
3. Storage overview page - save as "hpe-vme-03-storage-overview.png"

Use viewport 1920x1080 for consistency
Wait 3000ms for each page to fully load
```

### Phase 2: NFS Configuration Documentation

**Document NFS storage setup:**

```
Document my HPE VME NFS configuration at https://vme-server.lab:8443

Navigate to the NFS configuration section and capture:
1. NFS datastore list - save as "hpe-vme-nfs-01-datastores.png"
2. Add NFS datastore dialog - save as "hpe-vme-nfs-02-add-dialog.png"
3. NFS mount options - save as "hpe-vme-nfs-03-mount-options.png"
4. NFS permissions settings - save as "hpe-vme-nfs-04-permissions.png"

Wait for selector ".storage-content" on each page
Use full page screenshots
```

**Capture NFS configuration details:**

```
Capture detailed NFS configuration screenshots:

1. NFS server settings showing:
   - Server IP/hostname
   - Export path
   - Mount options
   Save as "hpe-vme-nfs-server-config.png"

2. NFS datastore properties showing:
   - Capacity
   - Free space
   - Connected hosts
   Save as "hpe-vme-nfs-datastore-properties.png"

Use element screenshots with selector ".config-panel" for cleaner captures
```

### Phase 3: iSCSI Configuration Documentation

**Document iSCSI initiator setup:**

```
Document HPE VME iSCSI configuration at https://vme-server.lab:8443

Capture iSCSI initiator configuration:
1. iSCSI adapter overview - save as "hpe-vme-iscsi-01-adapters.png"
2. iSCSI initiator settings - save as "hpe-vme-iscsi-02-initiator.png"
3. Discovery portal configuration - save as "hpe-vme-iscsi-03-discovery.png"
4. Target list - save as "hpe-vme-iscsi-04-targets.png"
5. LUN mapping - save as "hpe-vme-iscsi-05-luns.png"

Wait for selector ".iscsi-config" on each page
Viewport 1920x1080
```

**Capture iSCSI session details:**

```
Capture active iSCSI sessions on HPE VME:

1. Session list showing:
   - Target IQN
   - Portal IP
   - Session state
   Save as "hpe-vme-iscsi-sessions.png"

2. Multipath configuration showing:
   - Active paths
   - Path policy
   - Failover settings
   Save as "hpe-vme-iscsi-multipath.png"

Wait 2000ms for session data to populate
```

### Phase 4: Storage Array Integration

**Document storage array configuration (if using HPE storage):**

```
Capture HPE storage array configuration for VME integration:

From storage array management interface at https://storage-array.lab:

1. iSCSI target configuration - save as "hpe-storage-iscsi-targets.png"
2. Host/initiator groups - save as "hpe-storage-host-groups.png"
3. LUN assignments - save as "hpe-storage-lun-assignments.png"
4. NFS export configuration - save as "hpe-storage-nfs-exports.png"

Wait for selector ".storage-config" on each page
```

### Phase 5: Network Configuration

**Document network settings for storage traffic:**

```
Capture HPE VME network configuration for storage:

1. Network adapters overview - save as "hpe-vme-network-01-adapters.png"
2. Storage network VLAN config - save as "hpe-vme-network-02-vlans.png"
3. IP configuration for storage NICs - save as "hpe-vme-network-03-ip-config.png"
4. MTU settings (jumbo frames) - save as "hpe-vme-network-04-mtu.png"

Viewport 1600x900
Wait for network data to load
```

### Phase 6: Verification Screenshots

**Capture verification of working configuration:**

```
Verify and document working storage configuration:

1. VM storage assignment showing NFS datastore - save as "hpe-vme-verify-01-vm-nfs.png"
2. VM storage assignment showing iSCSI datastore - save as "hpe-vme-verify-02-vm-iscsi.png"
3. Storage performance metrics - save as "hpe-vme-verify-03-performance.png"
4. Active storage connections - save as "hpe-vme-verify-04-connections.png"

Full page screenshots
Wait 3000ms for metrics to populate
```

## Common HPE VME Selectors

Use these CSS selectors for element-specific screenshots:

```javascript
// Dashboard elements
".dashboard-summary"          // Main dashboard summary
".vm-status-panel"           // VM status overview
".storage-status-panel"      // Storage status

// Storage elements
".datastore-list"            // List of datastores
".storage-config-form"       // Storage configuration form
".nfs-mount-options"         // NFS mount options
".iscsi-adapter-config"      // iSCSI adapter settings

// Network elements
".network-adapter-list"      // Network adapter list
".vlan-config-table"         // VLAN configuration
".ip-settings-form"          // IP configuration form

// VM elements
".vm-list-table"             // Virtual machine list
".vm-storage-config"         // VM storage configuration
```

## Screenshot Naming Convention

For organized documentation, use this naming pattern:

```
hpe-vme-<category>-<sequence>-<description>.png

Examples:
- hpe-vme-nfs-01-overview.png
- hpe-vme-nfs-02-add-datastore.png
- hpe-vme-iscsi-01-initiator.png
- hpe-vme-iscsi-02-targets.png
- hpe-vme-network-01-adapters.png
- hpe-vme-verify-01-working.png
```

## Complete Documentation Example

**Full workflow for documenting a new HPE VME NFS setup:**

```
I need to document my HPE VME NFS configuration. Please capture:

Server: https://vme01.lab:8443
Viewport: 1920x1080
Wait 3000ms for each page

Screenshots needed:
1. Dashboard showing overall system status
   Save as: hpe-vme-nfs-01-dashboard.png

2. Navigate to Storage > Datastores
   Capture the datastore list
   Save as: hpe-vme-nfs-02-datastore-list.png

3. Click "Add NFS Datastore" (I'll do this manually)
   Capture the add datastore dialog
   Save as: hpe-vme-nfs-03-add-dialog.png

4. After configuration, capture the new NFS datastore properties
   Save as: hpe-vme-nfs-04-properties.png

5. Navigate to the VM that will use this storage
   Capture VM storage configuration
   Save as: hpe-vme-nfs-05-vm-storage.png

6. Capture storage performance metrics
   Wait for selector ".performance-chart"
   Save as: hpe-vme-nfs-06-performance.png
```

## Tips for HPE VME Screenshots

### 1. Authentication Handling

HPE VME sessions may timeout. Before starting:
- Log in to the web interface
- Keep the session active
- Capture all screenshots in one session

### 2. Wait for Dynamic Content

HPE VME loads data asynchronously:
```
Always use: waitForTimeout: 3000
Or wait for specific selectors like ".data-loaded"
```

### 3. Consistent Viewport

For professional documentation:
```
Standard: 1920x1080 (full HD)
Compact: 1600x900 (fits more on screen)
Wide: 2560x1440 (high detail)
```

### 4. Full Page vs Viewport

- **Full page**: Configuration wizards, long lists
- **Viewport**: Dashboards, summary pages
- **Element**: Specific tables, forms, dialogs

### 5. Browser Choice

```
Chromium: Best compatibility with HPE VME (recommended)
Firefox: Alternative if rendering issues
```

## Integration with Existing Guides

These screenshots can be integrated into your existing documentation structure:

```
Quickstart-Guides/
├── distributions/
│   └── hpe-vme/
│       ├── nfs/
│       │   ├── QUICKSTART.md
│       │   ├── BEST-PRACTICES.md
│       │   └── screenshots/
│       │       ├── hpe-vme-nfs-*.png
│       └── iscsi/
│           ├── QUICKSTART.md
│           ├── BEST-PRACTICES.md
│           └── screenshots/
│               ├── hpe-vme-iscsi-*.png
```

## Troubleshooting HPE VME Screenshots

### Self-Signed Certificate Issues

HPE VME typically uses self-signed certificates. Playwright handles these automatically, but if you encounter issues:

```
The server accepts self-signed certificates by default.
No additional configuration needed.
```

### Session Timeout

If screenshots fail due to session timeout:
1. Log in to HPE VME manually
2. Capture all screenshots quickly
3. Or increase session timeout in HPE VME settings

### Slow Page Load

HPE VME may load slowly on initial access:
```
Use: waitForTimeout: 5000
Or: waitForSelector: ".page-loaded"
```

## Next Steps

Once you have your HPE VME servers installed:

1. **Test connectivity**: Verify you can access the web interface
2. **Run initial capture**: Test with dashboard screenshot
3. **Document baseline**: Capture pre-configuration state
4. **Configure storage**: Set up NFS/iSCSI
5. **Document configuration**: Capture each step
6. **Verify setup**: Capture working state
7. **Create guides**: Integrate screenshots into markdown documentation

## Example Commands for Your Setup

```
# Initial test
Capture a screenshot of https://vme01.lab:8443

# Dashboard capture
Capture a full page screenshot of https://vme01.lab:8443/dashboard
Wait 3000ms and save as hpe-vme-dashboard.png

# Storage configuration
Navigate to https://vme01.lab:8443/storage
Wait for selector ".storage-panel"
Capture and save as hpe-vme-storage.png
```

Ready to document your HPE VME environment! 🚀

