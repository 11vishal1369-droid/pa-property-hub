#!/usr/bin/env bash
# Propertys Available: deploy on Ubuntu 22.04 VPS (201.18.206.131). Run as root from /opt/propertysavailable/deploy:
#   sudo CERT_EMAIL=you@example.com ./deploy.sh
# Installs Docker, runs `docker compose up -d --build`, gets one Let's Encrypt certificate for
# propertysavailable.com, www.propertysavailable.com and admin.propertysavailable.com, and sets up renewal.
set -euo pipefail

CERT_EMAIL="${CERT_EMAIL:-}"
DOMAIN=propertysavailable.com
NAMES=("$DOMAIN" "www.$DOMAIN" "admin.$DOMAIN")
cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo ./deploy.sh)"; exit 1; }
[ -f .env ] || { echo "Missing deploy/.env: copy .env.example to .env and fill it in"; exit 1; }
grep -qE '^(JWT_SECRET|AADHAAR_ENC_KEY|ADMIN_PASSWORD|APP_API_KEY|WEB_JWT_SECRET|WEB_EDITOR_PASSWORD)=("")?$' .env && { echo "Fill in all secrets in .env first"; exit 1; }

echo "==> Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
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

echo "==> Building and starting all containers (mongo, backend, webcontent, web)"
mkdir -p /var/www/certbot /etc/letsencrypt
docker compose up -d --build
docker compose ps

echo "==> TLS certificate for ${NAMES[*]}"
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  [ -n "$CERT_EMAIL" ] || { echo "Site is running with a temporary certificate. Re-run with CERT_EMAIL=you@example.com to get the real one."; exit 1; }
  ARGS=(); for n in "${NAMES[@]}"; do ARGS+=(-d "$n"); done
  docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot certbot/certbot certonly \
    --webroot -w /var/www/certbot --cert-name "$DOMAIN" --non-interactive --agree-tos -m "$CERT_EMAIL" "${ARGS[@]}"
  docker compose restart web
fi

echo "==> Certificate auto-renewal (daily)"
cat > /etc/cron.d/propertysavailable-certbot <<EOF
17 3 * * * root docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f $(pwd)/docker-compose.yml restart web
EOF

echo "==> Health check"
sleep 5
curl -fsS "https://$DOMAIN/api/" >/dev/null && echo "API ok"
curl -fsS "https://$DOMAIN/webcontent-api/" >/dev/null && echo "Website content service ok"
curl -fsS -o /dev/null "https://$DOMAIN/" && echo "Website ok: https://$DOMAIN/"
curl -fsS -o /dev/null "https://admin.$DOMAIN/admin/" && echo "Admin panel ok: https://admin.$DOMAIN/"
