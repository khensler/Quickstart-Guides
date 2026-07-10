## Quick Reference

| Command | Description |
|---------|-------------|
| `cat /sys/class/fc_host/host*/port_name` | List HBA WWPNs |
| `cat /sys/class/fc_host/host*/port_state` | Check HBA port link state |
| `cat /sys/class/fc_host/host*/speed` | Check negotiated link speed |
| `sudo rescan-scsi-bus.sh` | Scan for newly presented LUNs |
| `lsscsi` | List all SCSI/FC devices |
| `sudo multipath -ll` | Show multipath devices and path status |
| `sudo multipathd reconfigure` | Reload multipath configuration |
| `sudo systemctl restart multipathd` | Restart multipath daemon |

