```bash
# Create discovery configuration
sudo tee /etc/nvme/discovery.conf > /dev/null <<EOF
-t tcp -a <PORTAL_IP_1> -s 4420
-t tcp -a <PORTAL_IP_2> -s 4420
-t tcp -a <PORTAL_IP_3> -s 4420
-t tcp -a <PORTAL_IP_4> -s 4420
EOF

# Enable autoconnect service
sudo systemctl enable --now nvmf-autoconnect.service
```

