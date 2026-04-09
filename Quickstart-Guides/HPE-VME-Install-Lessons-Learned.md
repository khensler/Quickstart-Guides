# HPE VME Unified Installer - Lessons Learned

## Host Configuration
- **Host:** vme-3
- **Date:** 2026-03-20

## Hardware Overview
| Interface | Type | Purpose |
|-----------|------|---------|
| eno1, eno2 | Intel X550-TX 10GbE LOM | NOT USED |
| enp177s0f0np0, enp177s0f1np1 | Mellanox ConnectX-7 25GbE | Management Bond |
| enp177s0f2np2, enp177s0f3np3 | Mellanox ConnectX-7 25GbE | Compute Bond |
| ens1f0np0, ens1f1np1 | Mellanox ConnectX-6 Dx | Storage (VLAN 2230) |

---

## Step 1: Ubuntu Network Configuration (from HVM ISO)

### 1.1 Create Management Bond (bond0)

**Screenshot: Create bond dialog**

```
Name: bond0

Devices Selected:
  [X] enp177s0f0np0
  [X] enp177s0f1np1
  [ ] enp177s0f2np2
  [ ] enp177s0f3np3
  [ ] ens1f0np0
  [ ] ens1f1np1

Bond mode:        [ active-backup ]
XMIT hash policy: [ layer2 ]
LACP rate:        [ slow ]
```

**Click [ Create ]**

---

### 1.2 Create Compute Bond (bond1)

**Screenshot: Create bond dialog for bond1**

```
Name: bond1

Devices Selected:
  [ ] eno1
  [ ] eno2
  [ ] enp177s0f0np0
  [ ] enp177s0f1np1
  [X] enp177s0f2np2
  [X] enp177s0f3np3
  [ ] ens1f0np0
  [ ] ens1f1np1

Bond mode:        [ active-backup ]
XMIT hash policy: [ layer2 ]
LACP rate:        [ slow ]
```

**Click [ Create ]**

---

### 1.3 Configure VLANs

**Management VLAN on bond0:**
- VLAN ID: (your mgmt VLAN)
- Static IP: (your host IP)
- Gateway: (your gateway)
- DNS: (your DNS)

**Compute VLAN on bond1:**
- VLAN ID: (your compute VLAN)
- No IP needed (used for VM traffic)

---

### 1.4 Storage Network Configuration

Configure storage interfaces with VLAN 2230:
- ens1f0np0.2230
- ens1f1np1.2230

---

## Step 2: Create Cluster from VME Manager GUI

**Important:** Do NOT use `hpe-vm` console to add workers. Use the VME Manager GUI instead.

### 2.1 Prepare All Hosts First
- Install Ubuntu from HVM ISO on all 3 hosts
- Configure bonds and VLANs on each host during Ubuntu install
- Ensure all hosts have static IPs and can reach each other

### 2.2 Create Cluster with All 3 Hosts at Once
1. Log into VME Manager: https://10.21.146.100
2. Go to **Infrastructure > Clusters**
3. Click **+ ADD CLUSTER** and select **HPE VM**
4. Select **non-HCI Layout** (since using external Pure storage, not Ceph)
5. Add all 3 hosts in the wizard:
   - SSH Host: IP address of each host
   - SSH Username/Password: user with sudo access
   - SSH Key: (optional)
6. Configure network interfaces:
   - Management Interface: bond0 (or bond0.VLAN)
   - Compute Interface: bond1 (or bond1.VLAN)
   - Storage Interface: (leave empty, Pure added later)
   - Data Device: (leave empty for non-HCI)
7. Set Compute VLANs as needed
8. Click Create

### 2.3 Add Pure Storage Later
- Add Pure FlashArray as external datastore after cluster is created
- Storage interfaces (ens1f0np0, ens1f1np1) used for Pure connectivity

---

## Key Lessons Learned

1. **Add all hosts via VME Manager GUI** - Do NOT use `hpe-vm` console "Install VME Worker". Use Infrastructure > Clusters > + ADD CLUSTER and add all hosts at once.

2. **Non-HCI for external storage** - Select non-HCI Layout when using Pure storage (no Ceph needed)

3. **Verify network connectivity** between all hosts BEFORE proceeding with VME setup

4. **Separate bonds for mgmt/compute** is cleaner than converged networking

5. **Management switch ports must be access mode on VLAN 2146** - NOT trunk mode. Compute switch ports must be trunked for VLAN 2244 tagging. Verify with Arista `show interfaces switchport` on the specific breakout sub-interface (e.g., Ethernet49/1), not just the parent port.

6. **VME Manager goes on management network** - same subnet as host management IPs

7. **iSCSI `sendtargets` returns ALL portals — filter before login.** When running `iscsiadm -m discovery -t sendtargets` against a Pure FlashArray, the array responds with **every** portal IP it knows about, including portals on VLANs/subnets you are not using (e.g., VLAN 2245 / 10.21.245.x in our case). If you then run `iscsiadm -m node -l`, it attempts to login to all of them — the unreachable ones time out and clutter the output with errors.

   **Complete iSCSI setup procedure — run on EACH host (vme-1, vme-2, vme-3):**
   ```bash
   # SSH to each host in turn:
   #   vme-1: ssh -o StrictHostKeyChecking=no admin@10.21.146.102
   #   vme-2: ssh -o StrictHostKeyChecking=no admin@10.21.146.104
   #   vme-3: ssh -o StrictHostKeyChecking=no admin@10.21.146.206

   # Clean up
   sudo iscsiadm -m node -u 2>/dev/null
   sudo iscsiadm -m node -o delete 2>/dev/null

   # Create iface bindings (verify interface names with: ip addr show | grep 2230)
   sudo iscsiadm -m iface -I ens1f0np0.2230 --op=new
   sudo iscsiadm -m iface -I ens1f0np0.2230 --op=update -n iface.net_ifacename -v ens1f0np0.2230
   sudo iscsiadm -m iface -I ens1f1np1.2230 --op=new
   sudo iscsiadm -m iface -I ens1f1np1.2230 --op=update -n iface.net_ifacename -v ens1f1np1.2230

   # Discover
   sudo iscsiadm -m discovery -t sendtargets -p 192.168.0.11:3260 -I ens1f0np0.2230
   sudo iscsiadm -m discovery -t sendtargets -p 192.168.0.12:3260 -I ens1f0np0.2230
   sudo iscsiadm -m discovery -t sendtargets -p 192.168.1.11:3260 -I ens1f1np1.2230
   sudo iscsiadm -m discovery -t sendtargets -p 192.168.1.12:3260 -I ens1f1np1.2230

   # Delete the unwanted 10.21.245.x nodes BEFORE login
   sudo iscsiadm -m node -o delete -p 10.21.245.18:3260
   sudo iscsiadm -m node -o delete -p 10.21.245.19:3260
   sudo iscsiadm -m node -o delete -p 10.21.245.20:3260
   sudo iscsiadm -m node -o delete -p 10.21.245.21:3260

   # Login only to 192.168.x.x targets
   sudo iscsiadm -m node -l

   # Set auto-login on boot
   sudo iscsiadm -m node -o update -n node.startup -v automatic

   # Verify
   sudo iscsiadm -m session
   sudo multipath -ll
   ```

   Should show 4 active sessions on 192.168.x.x and 4 multipath paths to the Pure volume.

8. **All cluster hosts must have iSCSI/multipath configured before adding a GFS2 datastore.** The VME Manager UI will **not** show the multipath device in the datastore creation wizard until **every host** in the cluster can see it. If you configure iSCSI and multipath on only one or two hosts, the disk simply won't appear when you go to Infrastructure > Clusters > [Cluster] > Storage > Data Stores > ADD > GFS2 Pool. Complete Steps 1–6 (iface binding, discovery, portal cleanup, login, multipath verification) on **all 3 hosts** before attempting to create the datastore in the UI.

   Additionally, the VME Manager's built-in iSCSI discovery (under the cluster Storage > iSCSI tab) is a basic `sendtargets` convenience feature. It does **not** support iface binding or portal filtering, so for dual-fabric / multi-VLAN storage environments (like Pure Storage), CLI configuration on each host is a **mandatory prerequisite** — the UI alone cannot handle this topology.

---

## Network IPs
| Host | IP |
|------|-----|
| vme-1 | 10.21.146.102 |
| vme-2 | 10.21.146.104 |
| vme-3 | 10.21.146.206 |
| VME Manager | 10.21.146.100 |
| Gateway | (your gateway) |

