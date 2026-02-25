```bash
sudo mkdir -p /etc/nvme
sudo nvme gen-hostnqn | sudo tee /etc/nvme/hostnqn
cat /etc/nvme/hostnqn
```

**Register this NQN** with your storage array's allowed hosts list.

