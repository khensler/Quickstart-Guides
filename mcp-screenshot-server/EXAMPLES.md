# Usage Examples

Real-world examples for using the MCP Screenshot Server in lab environments.

## Basic Examples

### Simple Screenshot

**Request**:
```
Capture a screenshot of https://example.com
```

**What happens**:
- Opens Chromium browser
- Navigates to example.com
- Captures viewport screenshot (1280x720)
- Saves to `screenshots/screenshot-TIMESTAMP.png`

### Full Page Screenshot

**Request**:
```
Capture a full page screenshot of https://github.com
```

**What happens**:
- Captures entire scrollable page
- Useful for long documentation pages

### Custom Viewport

**Request**:
```
Capture a screenshot of https://example.com with width 1920 and height 1080
```

**What happens**:
- Sets viewport to 1920x1080
- Captures at specified resolution
- Useful for consistent documentation

## Lab Environment Examples

### Proxmox VE Documentation

**Scenario**: Document Proxmox cluster setup

**Request**:
```
Capture screenshots of my Proxmox environment:
1. Dashboard at https://proxmox.lab:8006
2. Storage configuration page
3. Network settings page

Use browser chromium, wait 3000ms for each page to load, and save as:
- proxmox-dashboard.png
- proxmox-storage.png  
- proxmox-network.png
```

**Result**: Three consistent screenshots for documentation

### Storage Array Interface

**Scenario**: Document Pure Storage FlashArray configuration

**Request**:
```
Capture full page screenshots of:
- https://flasharray.lab/storage/volumes
- https://flasharray.lab/storage/hosts
- https://flasharray.lab/storage/protection

Wait for selector ".data-loaded" on each page
Save with viewport 1920x1080
```

**Result**: High-resolution storage configuration screenshots

### Network Switch Configuration

**Scenario**: Document switch VLAN configuration

**Request**:
```
Navigate to https://switch.lab/vlans and capture a screenshot of the 
VLAN table using selector "table.vlan-config"
```

**Result**: Screenshot of just the VLAN table

## Advanced Examples

### Multi-Browser Testing

**Request**:
```
Capture screenshots of https://app.lab/dashboard using:
1. Chromium browser
2. Firefox browser
3. WebKit browser

Save as dashboard-chromium.png, dashboard-firefox.png, dashboard-webkit.png
```

**Result**: Compare rendering across browsers

### Element-Specific Capture

**Request**:
```
Capture screenshots of these specific elements on https://monitoring.lab:
1. CPU graph: selector "#cpu-graph"
2. Memory graph: selector "#memory-graph"
3. Network graph: selector "#network-graph"
```

**Result**: Individual graph screenshots for reports

### Clipping Region

**Request**:
```
Capture a screenshot of https://dashboard.lab with clip region:
- x: 100
- y: 200
- width: 800
- height: 600
```

**Result**: Screenshot of specific screen region

### Wait for Dynamic Content

**Request**:
```
Capture a screenshot of https://app.lab/reports
Wait for selector ".report-loaded"
Then wait an additional 2000ms for animations to complete
```

**Result**: Screenshot after all content and animations load

## Documentation Workflow Examples

### Creating a Setup Guide

**Scenario**: Document iSCSI configuration steps

**Request**:
```
I'm creating an iSCSI setup guide. Capture screenshots of:

1. Initial configuration page at https://storage.lab/iscsi/config
   - Wait for selector ".config-form"
   - Save as "01-iscsi-initial-config.png"

2. Target creation page at https://storage.lab/iscsi/targets
   - Wait for selector ".target-list"
   - Save as "02-iscsi-targets.png"

3. LUN mapping page at https://storage.lab/iscsi/luns
   - Wait for selector ".lun-table"
   - Save as "03-iscsi-luns.png"

Use viewport 1600x900 for all screenshots
```

**Result**: Numbered, consistent screenshots for step-by-step guide

### Troubleshooting Documentation

**Scenario**: Document an error state

**Request**:
```
Capture a screenshot of the error panel on https://app.lab/dashboard
Use selector ".error-panel"
Save as "error-state-example.png"
```

**Result**: Screenshot of error for troubleshooting guide

### Before/After Comparison

**Scenario**: Show configuration changes

**Request**:
```
Capture screenshots for before/after comparison:

1. Before: https://switch.lab/config/vlans
   - Save as "vlans-before.png"

2. (Make configuration changes manually)

3. After: https://switch.lab/config/vlans
   - Save as "vlans-after.png"

Use same viewport (1920x1080) for both
```

**Result**: Consistent before/after screenshots

## Training Material Examples

### Creating Consistent Screenshots

**Request**:
```
Create training screenshots for new admins:

Capture full page screenshots of:
1. https://proxmox.lab:8006 - "training-01-login.png"
2. https://proxmox.lab:8006/#v1:0:=node/pve - "training-02-node-view.png"
3. https://proxmox.lab:8006/#v1:0:=storage - "training-03-storage.png"

Use viewport 1440x900 (standard training resolution)
Wait 3000ms for each page to fully load
```

**Result**: Consistent training materials

### Interactive Element Capture

**Request**:
```
Capture screenshots of UI elements for training:

From https://app.lab/admin:
1. Navigation menu: selector "nav.sidebar"
2. User profile dropdown: selector ".user-menu"
3. Settings panel: selector "#settings-panel"

Save as menu.png, profile.png, settings.png
```

**Result**: Individual UI component screenshots

## Monitoring Examples

### Dashboard Snapshots

**Request**:
```
Capture current state of monitoring dashboards:

1. https://grafana.lab/d/system - "monitoring-system.png"
2. https://grafana.lab/d/storage - "monitoring-storage.png"
3. https://grafana.lab/d/network - "monitoring-network.png"

Wait for selector ".panel-container" on each
Full page screenshots
```

**Result**: Current monitoring state for reports

### Status Page Capture

**Request**:
```
Capture the status page at https://status.lab
Wait for selector ".status-grid"
Save as "system-status-TIMESTAMP.png"
```

**Result**: Timestamped status snapshot

## Testing Examples

### Page Load Verification

**Request**:
```
Verify these pages load correctly:
1. https://app1.lab
2. https://app2.lab
3. https://app3.lab

Navigate to each and wait for selector ".app-ready"
Report load times
```

**Result**: Verification that all apps are accessible

### Responsive Design Testing

**Request**:
```
Test responsive design of https://app.lab:

1. Desktop: 1920x1080
2. Tablet: 768x1024
3. Mobile: 375x667

Capture screenshots at each resolution
```

**Result**: Screenshots at different viewport sizes

## Batch Operations

### Multiple Pages, Same Site

**Request**:
```
Capture all configuration pages from https://router.lab:

/config/interfaces - "router-interfaces.png"
/config/routing - "router-routing.png"
/config/firewall - "router-firewall.png"
/config/nat - "router-nat.png"

Use Firefox browser
Wait 2000ms for each page
```

**Result**: Complete router configuration documentation

### Multiple Sites, Same Page

**Request**:
```
Capture dashboards from all lab systems:

https://proxmox1.lab:8006 - "proxmox1-dashboard.png"
https://proxmox2.lab:8006 - "proxmox2-dashboard.png"
https://proxmox3.lab:8006 - "proxmox3-dashboard.png"

Viewport 1600x900
Wait for selector ".pve-content"
```

**Result**: Dashboard screenshots from all cluster nodes

## Tips for Best Results

1. **Use consistent viewports** for documentation
2. **Wait for selectors** instead of fixed timeouts when possible
3. **Name files descriptively** for easy organization
4. **Use full page** for long content, viewport for specific views
5. **Test selectors** in browser DevTools first
6. **Consider browser choice** - Chromium for most cases, Firefox/WebKit for compatibility testing

