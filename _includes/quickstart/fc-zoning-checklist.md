> **Before continuing, confirm the following on your FC fabric and storage array:**
>
> - [ ] **HBA WWPNs collected** from all hosts (Step 2 above)
> - [ ] **Single-initiator zoning configured** on the FC switch — each host WWPN zoned individually with the target array ports (not all initiators in one zone)
> - [ ] **Host entry created** on the FlashArray with the host's WWPN(s) and OS type set to `Linux`
> - [ ] **Host Group created** (for clusters) and all host entries added
> - [ ] **Volume connected** to the host or host group on the FlashArray
>
> LUNs will not be visible to the host until the volume is connected and zoning is in place. If you do not administer the FC fabric or array yourself, coordinate with your SAN and storage administrators before proceeding.

