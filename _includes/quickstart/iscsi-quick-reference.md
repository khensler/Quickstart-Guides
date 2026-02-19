## Quick Reference

| Command | Description |
|---------|-------------|
| `sudo iscsiadm -m session` | List active iSCSI sessions |
| `sudo iscsiadm -m discovery -t sendtargets -p <IP>:3260` | Discover targets |
| `sudo iscsiadm -m node -T <IQN> -p <IP>:3260 --login` | Login to target |
| `sudo iscsiadm -m node -T <IQN> -p <IP>:3260 --logout` | Logout from target |
| `sudo multipath -ll` | Show multipath devices |

