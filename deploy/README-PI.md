# Raspberry Pi 5 Deployment

## Prerequisites
```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in, then:
docker --version
```

## Deploy

```bash
# 1. Clone repo to Pi
git clone <your-repo-url> /opt/pl-dashboard
cd /opt/pl-dashboard

# 2. Copy your .env file
cp backend/.env.example backend/.env
# Edit with your keys: nano backend/.env

# 3. Copy your dumps data
# scp -r backend/dumps/ pi@<pi-ip>:/opt/pl-dashboard/backend/dumps/

# 4. Build and run
docker compose up -d --build

# 5. Verify
curl http://localhost:9999/api/auth/status
```

## Auto-start on boot (systemd)

```bash
sudo cp deploy/pl-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pl-dashboard
sudo systemctl start pl-dashboard

# Check status
sudo systemctl status pl-dashboard

# View logs
sudo journalctl -u pl-dashboard -f
```

## Add Cloudflare Tunnel

```bash
# Install cloudflared on Pi
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Login and create tunnel
cloudflared tunnel login
cloudflared tunnel create pl-dashboard
cloudflared tunnel route dns pl-dashboard yourdomain.com

# Create config
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/config.yml << 'EOF'
tunnel: <TUNNEL_ID>
credentials-file: /home/$USER/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: yourdomain.com
    service: http://127.0.0.1:9999
  - service: http_status:404
EOF

# Install as system service (auto-starts on boot)
sudo cloudflared service install
sudo systemctl start cloudflared
```

## Useful commands
```bash
docker compose logs -f        # View logs
docker compose restart         # Restart app
docker compose down            # Stop
docker compose up -d --build   # Rebuild after code changes
```
