# HPE VME Screenshot Templates

Ready-to-use templates for documenting HPE Virtual Machine Essentials configurations.

## Quick Templates

Copy and paste these templates, then customize with your server details.

---

## Template 1: Complete NFS Documentation

```
Document my HPE VME NFS storage configuration:

Server: https://YOUR-VME-SERVER:8443
Viewport: 1920x1080
Browser: chromium
Wait: 3000ms for each page

Please capture the following screenshots:

1. Main dashboard
   Save as: hpe-vme-nfs-01-dashboard.png

2. Storage > Datastores page
   Save as: hpe-vme-nfs-02-datastores.png

3. NFS datastore configuration showing:
   - NFS server IP
   - Export path
   - Mount options
   Save as: hpe-vme-nfs-03-config.png

4. NFS datastore properties showing capacity and usage
   Save as: hpe-vme-nfs-04-properties.png

5. Virtual machine storage assignment using NFS
   Save as: hpe-vme-nfs-05-vm-assignment.png

Use full page screenshots for all captures.
```

---

## Template 2: Complete iSCSI Documentation

```
Document my HPE VME iSCSI storage configuration:

Server: https://YOUR-VME-SERVER:8443
Viewport: 1920x1080
Browser: chromium
Wait: 3000ms for each page

Please capture the following screenshots:

1. Storage adapters overview
   Save as: hpe-vme-iscsi-01-adapters.png

2. iSCSI initiator configuration showing:
   - Initiator IQN
   - Adapter settings
   Save as: hpe-vme-iscsi-02-initiator.png

3. iSCSI discovery portal configuration
   Save as: hpe-vme-iscsi-03-discovery.png

4. iSCSI targets list showing:
   - Target IQN
   - Portal addresses
   - Connection status
   Save as: hpe-vme-iscsi-04-targets.png

5. iSCSI LUN mapping
   Save as: hpe-vme-iscsi-05-luns.png

6. Multipath configuration
   Save as: hpe-vme-iscsi-06-multipath.png

7. Active iSCSI sessions
   Save as: hpe-vme-iscsi-07-sessions.png

Use full page screenshots for all captures.
```

---

## Template 3: Network Configuration for Storage

```
Document my HPE VME network configuration for storage traffic:

Server: https://YOUR-VME-SERVER:8443
Viewport: 1920x1080
Wait: 3000ms for each page

Please capture:

1. Network adapters overview
   Save as: hpe-vme-network-01-adapters.png

2. Storage network VLAN configuration
   Save as: hpe-vme-network-02-vlans.png

3. IP configuration for storage NICs showing:
   - IP addresses
   - Subnet masks
   - Gateway settings
   Save as: hpe-vme-network-03-ip-config.png

4. MTU settings (jumbo frames for storage)
   Save as: hpe-vme-network-04-mtu.png

5. Network performance metrics
   Save as: hpe-vme-network-05-performance.png
```

---

## Template 4: Quick Dashboard Capture

```
Capture a quick overview of my HPE VME server:

URL: https://YOUR-VME-SERVER:8443/dashboard
Viewport: 1920x1080
Full page: yes
Wait: 3000ms
Save as: hpe-vme-dashboard-TIMESTAMP.png
```

---

## Template 5: Storage Array Integration

```
Document storage array configuration for HPE VME:

Storage Array: https://YOUR-STORAGE-ARRAY/

Please capture:

1. iSCSI target configuration
   Save as: storage-array-iscsi-targets.png

2. Host groups showing VME initiators
   Save as: storage-array-host-groups.png

3. LUN assignments to VME hosts
   Save as: storage-array-lun-assignments.png

4. NFS export configuration for VME
   Save as: storage-array-nfs-exports.png

Viewport: 1920x1080
Wait: 2000ms for each page
```

---

## Template 6: Before/After Configuration

```
Document before and after states of HPE VME storage configuration:

Server: https://YOUR-VME-SERVER:8443
Viewport: 1920x1080

BEFORE configuration:
1. Capture current storage overview
   Save as: hpe-vme-before-storage.png

2. Capture current datastore list
   Save as: hpe-vme-before-datastores.png

(I will make configuration changes manually)

AFTER configuration:
3. Capture updated storage overview
   Save as: hpe-vme-after-storage.png

4. Capture updated datastore list
   Save as: hpe-vme-after-datastores.png

5. Capture new datastore properties
   Save as: hpe-vme-after-new-datastore.png
```

---

## Template 7: Troubleshooting Documentation

```
Document an issue with HPE VME storage:

Server: https://YOUR-VME-SERVER:8443

Please capture:

1. Error message or alert panel
   Use selector: ".alert-panel" or ".error-message"
   Save as: hpe-vme-error-state.png

2. Storage connection status showing failed connections
   Save as: hpe-vme-connection-status.png

3. System logs showing error details
   Save as: hpe-vme-error-logs.png

4. Storage adapter status
   Save as: hpe-vme-adapter-status.png

Wait 2000ms for each page
```

---

## Template 8: Performance Monitoring

```
Capture HPE VME storage performance metrics:

Server: https://YOUR-VME-SERVER:8443

Please capture:

1. Storage performance dashboard
   Wait for selector: ".performance-chart"
   Save as: hpe-vme-perf-01-dashboard.png

2. IOPS metrics for datastores
   Save as: hpe-vme-perf-02-iops.png

3. Throughput metrics
   Save as: hpe-vme-perf-03-throughput.png

4. Latency metrics
   Save as: hpe-vme-perf-04-latency.png

Full page screenshots
Wait 5000ms for metrics to populate
```

---

## Template 9: Multi-Server Documentation

```
Document multiple HPE VME servers in a cluster:

Viewport: 1920x1080
Wait: 3000ms for each

Server 1: https://vme01.lab:8443
- Capture dashboard: hpe-vme01-dashboard.png
- Capture storage: hpe-vme01-storage.png

Server 2: https://vme02.lab:8443
- Capture dashboard: hpe-vme02-dashboard.png
- Capture storage: hpe-vme02-storage.png

Server 3: https://vme03.lab:8443
- Capture dashboard: hpe-vme03-dashboard.png
- Capture storage: hpe-vme03-storage.png
```

---

## Template 10: Step-by-Step Configuration Guide

```
Create step-by-step screenshots for HPE VME NFS configuration guide:

Server: https://YOUR-VME-SERVER:8443
Viewport: 1600x900 (good for documentation)
Wait: 3000ms for each page

Step 1: Navigate to Storage section
Save as: step-01-navigate-storage.png

Step 2: Click "Add Datastore" button
Save as: step-02-add-datastore-button.png

Step 3: Select "NFS" as datastore type
Save as: step-03-select-nfs.png

Step 4: Enter NFS server details
Save as: step-04-nfs-server-details.png

Step 5: Configure mount options
Save as: step-05-mount-options.png

Step 6: Review and confirm
Save as: step-06-review-confirm.png

Step 7: Verify datastore is added
Save as: step-07-verify-added.png

Step 8: Check datastore properties
Save as: step-08-datastore-properties.png
```

---

## Customization Guide

### Replace These Placeholders:

- `YOUR-VME-SERVER` → Your actual VME server hostname/IP
- `YOUR-STORAGE-ARRAY` → Your storage array hostname/IP
- `TIMESTAMP` → Will be auto-generated
- Port numbers (`:8443`) → Adjust if using different ports

### Adjust These Settings:

**Viewport sizes:**
- `1920x1080` - Full HD, professional documentation
- `1600x900` - Compact, fits more content
- `2560x1440` - High detail, large displays

**Wait times:**
- `2000ms` - Fast loading pages
- `3000ms` - Standard (recommended)
- `5000ms` - Slow pages or heavy metrics

**Browser choice:**
- `chromium` - Best compatibility (recommended)
- `firefox` - Alternative rendering
- `webkit` - Safari-like rendering

### Common Selectors for HPE VME:

```
.dashboard-panel
.storage-overview
.datastore-list
.iscsi-config
.network-adapter-table
.vm-list
.performance-metrics
.alert-panel
.config-form
```

---

## Usage Tips

1. **Copy template** to your conversation with Claude
2. **Replace placeholders** with your actual server details
3. **Adjust settings** as needed for your environment
4. **Run the template** - Claude will capture all screenshots
5. **Review output** in the `screenshots/` directory

## Batch Processing

You can combine multiple templates:

```
I need to document my complete HPE VME setup.

First, use Template 1 for NFS configuration
Then, use Template 2 for iSCSI configuration
Finally, use Template 3 for network configuration

Server: https://vme01.lab:8443
Use consistent viewport: 1920x1080
```

---

Ready to document your HPE Virtual Machine Essentials environment! 🚀

