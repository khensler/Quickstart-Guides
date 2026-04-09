# HPE VME Quick Reference Card

Fast reference for capturing HPE Virtual Machine Essentials screenshots.

## Common Commands

### Quick Dashboard Capture
```
Capture a screenshot of https://vme.lab:8443
Wait 3000ms and save as vme-dashboard.png
```

### NFS Configuration
```
Capture full page screenshot of https://vme.lab:8443/storage
Wait for selector ".datastore-list"
Save as vme-nfs-datastores.png
```

### iSCSI Configuration
```
Capture screenshot of https://vme.lab:8443/storage/iscsi
Wait 3000ms
Save as vme-iscsi-config.png
```

### Network Settings
```
Capture screenshot of https://vme.lab:8443/network
Wait for selector ".network-adapters"
Save as vme-network-config.png
```

## Standard Settings

**Recommended viewport:** 1920x1080
**Recommended wait time:** 3000ms
**Recommended browser:** chromium
**Default port:** 8443 (HTTPS)

## File Naming Convention

```
hpe-vme-<category>-<sequence>-<description>.png

Categories:
- nfs        (NFS storage)
- iscsi      (iSCSI storage)
- network    (Network config)
- vm         (Virtual machines)
- dashboard  (Overview/dashboard)
- verify     (Verification screenshots)
```

## Common HPE VME URLs

Replace `vme.lab` with your server:

```
Dashboard:        https://vme.lab:8443/
Storage:          https://vme.lab:8443/storage
iSCSI:            https://vme.lab:8443/storage/iscsi
Network:          https://vme.lab:8443/network
Virtual Machines: https://vme.lab:8443/vms
Settings:         https://vme.lab:8443/settings
```

## Common Selectors

```css
.dashboard-summary      /* Main dashboard */
.datastore-list        /* Storage datastores */
.iscsi-config          /* iSCSI configuration */
.network-adapters      /* Network adapters */
.vm-list               /* Virtual machine list */
.storage-config-form   /* Storage config forms */
.alert-panel           /* Alerts/errors */
```

## Quick Templates

### Document NFS Setup
```
Document HPE VME NFS at https://vme.lab:8443
Capture: dashboard, storage list, NFS config, datastore properties
Viewport: 1920x1080, Wait: 3000ms
Save as: hpe-vme-nfs-01.png through hpe-vme-nfs-04.png
```

### Document iSCSI Setup
```
Document HPE VME iSCSI at https://vme.lab:8443
Capture: initiator config, discovery, targets, sessions
Viewport: 1920x1080, Wait: 3000ms
Save as: hpe-vme-iscsi-01.png through hpe-vme-iscsi-04.png
```

### Verify Configuration
```
Verify HPE VME storage at https://vme.lab:8443
Capture: storage overview, active connections, performance
Full page screenshots, Wait: 3000ms
```

## Troubleshooting Quick Fixes

**Page won't load:**
```
Increase wait time to 5000ms
Or use: waitForSelector ".page-loaded"
```

**Session timeout:**
```
Log in manually first
Capture all screenshots quickly
```

**Self-signed cert:**
```
No action needed - Playwright handles automatically
```

## Multi-Server Capture

```
Capture dashboards from all VME servers:
- https://vme01.lab:8443 → vme01-dashboard.png
- https://vme02.lab:8443 → vme02-dashboard.png
- https://vme03.lab:8443 → vme03-dashboard.png
Viewport: 1920x1080, Wait: 3000ms
```

## Integration with Documentation

Screenshots save to: `mcp-screenshot-server/screenshots/`

Organize into your guide structure:
```
Quickstart-Guides/
└── distributions/
    └── hpe-vme/
        ├── nfs/
        │   ├── QUICKSTART.md
        │   └── screenshots/
        └── iscsi/
            ├── QUICKSTART.md
            └── screenshots/
```

## Full Documentation Workflow

1. **Initial capture** - Dashboard and overview
2. **NFS setup** - Configuration steps
3. **iSCSI setup** - Initiator and targets
4. **Network config** - Storage network
5. **Verification** - Working state
6. **Performance** - Metrics and monitoring

See [HPE-VME-WORKFLOW.md](HPE-VME-WORKFLOW.md) for complete workflow.

## Ready-to-Use Templates

See [HPE-VME-TEMPLATES.md](HPE-VME-TEMPLATES.md) for:
- Complete NFS documentation template
- Complete iSCSI documentation template
- Network configuration template
- Before/after templates
- Troubleshooting templates
- Step-by-step guide templates

---

**Quick Start:** Copy a template, replace `vme.lab` with your server, and run!

