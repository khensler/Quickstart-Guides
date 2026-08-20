```bash
sudo mkdir -p /etc/nvme
sudo nvme gen-hostnqn | sudo tee /etc/nvme/hostnqn
cat /etc/nvme/hostnqn
```

**Register this NQN** with your storage array's allowed hosts list.

> **Cloned or template-deployed hosts: regenerate this.** A VM cloned from a
> template inherits the template's `/etc/nvme/hostnqn` byte-for-byte. Two hosts
> presenting the same NQN collapse onto a single array host object, so volumes
> intended for one are visible to both. This is easy to miss because the iSCSI
> initiator name is usually regenerated per host while the NQN is not — an
> environment that behaves correctly over iSCSI can be silently broken over NVMe.
>
> Confirm uniqueness across every host before connecting:
>
> ```bash
> # regenerate from the (per-host) hostid, or with nvme gen-hostnqn
> echo "nqn.2014-08.org.nvmexpress:uuid:$(cat /etc/nvme/hostid)" | \
>     sudo tee /etc/nvme/hostnqn
> ```
