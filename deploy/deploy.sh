#!/usr/bin/env bash
# Propertys Available on an aaPanel VPS (201.18.206.131). Run as root from /opt/propertysavailable/deploy:
#   sudo ./deploy.sh
# Installs Docker if missing and runs `docker compose up -d --build`. HTTPS and domains are handled by aaPanel's Nginx.
set -euo pipefail
cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo ./deploy.sh)"; exit 1; }
[ -f .env ] || { echo "Missing deploy/.env: copy .env.example to .env and fill it in"; exit 1; }
grep -qE '^(JWT_SECRET|AADHAAR_ENC_KEY|ADMIN_PASSWORD|APP_API_KEY|WEB_JWT_SECRET|WEB_EDITOR_PASSWORD)=("")?$' .env && { echo "Fill in all secrets in .env first"; exit 1; }

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker Engine + Compose plugin"
  apt-get update -y
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
fi

echo "==> Building and starting mongo, backend, webcontent, website, admin"
docker compose up -d --build
docker compose ps

echo "==> Health check (waiting for services)"
check() {
  for _ in $(seq 1 30); do curl -fsS -o /dev/null "$2" && { echo "  ok  $1  $2"; return 0; }; sleep 2; done
  echo "  FAIL $1  $2"; return 1
}
ok=0
check "Backend API" "http://127.0.0.1:5000/api/" || ok=1
check "Website content service" "http://127.0.0.1:5001/webcontent-api/" || ok=1
check "Main website" "http://127.0.0.1:3000/" || ok=1
check "Admin panel" "http://127.0.0.1:3001/admin/" || ok=1
[ "$ok" -eq 0 ] && echo "All services running. Now set up the reverse proxies in aaPanel (see README.md)." || { echo "Some services failed: docker compose logs <service>"; exit 1; }
