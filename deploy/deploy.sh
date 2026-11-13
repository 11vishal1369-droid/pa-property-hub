#!/usr/bin/env bash
# PA Super Admin: deploy on Ubuntu 22.04 (Hostinger VPS). Run as root from the deploy/ directory:
#   sudo ./deploy.sh
# Uses prebuilt images if BACKEND_IMAGE / WEB_IMAGE point to a registry, otherwise builds from this source tree.
set -euo pipefail

CERT_EMAIL="${CERT_EMAIL:-}"
cd "$(dirname "$0")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo ./deploy.sh)"; exit 1; }
[ -f .env ] || { echo "Missing deploy/.env: copy .env.example to .env and fill it in"; exit 1; }
grep -qE '^(JWT_SECRET|AADHAAR_ENC_KEY|ADMIN_PASSWORD|APP_API_KEY)=("")?$' .env && { echo "Fill in all secrets in .env first"; exit 1; }
envval() { grep -E "^$1=" .env | head -n1 | cut -d= -f2- | sed -E 's/^"(.*)"$/\1/'; }
BACKEND_IMAGE="$(envval BACKEND_IMAGE)"; WEB_IMAGE="$(envval WEB_IMAGE)"
DOMAIN="${DOMAIN:-$(envval PUBLIC_BASE_URL | sed -E 's#^https?://##; s#/.*$##')}"
DOMAIN="${DOMAIN:-propertysavailable.com}"

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

echo "==> Getting images"
if [[ "${BACKEND_IMAGE:-}" == */* && "${WEB_IMAGE:-}" == */* ]]; then
  docker compose pull
else
  echo "    No registry images set; building from source"
  docker compose build
fi

echo "==> TLS certificate for $DOMAIN"
mkdir -p /var/www/certbot /etc/letsencrypt
if [ ! -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
  [ -n "$CERT_EMAIL" ] || { echo "Set CERT_EMAIL=you@example.com to request a Let's Encrypt certificate"; exit 1; }
  docker compose stop web 2>/dev/null || true
  docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt certbot/certbot certonly --standalone \
    --non-interactive --agree-tos -m "$CERT_EMAIL" -d "$DOMAIN" -d "www.$DOMAIN"
fi

echo "==> Starting containers"
docker compose up -d
docker compose ps

echo "==> Certificate auto-renewal (daily)"
cat > /etc/cron.d/pa-admin-certbot <<EOF
17 3 * * * root docker run --rm -v /etc/letsencrypt:/etc/letsencrypt -v /var/www/certbot:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && docker compose -f $(pwd)/docker-compose.yml exec -T web nginx -s reload
EOF

echo "==> Health check"
sleep 5
curl -fsS "https://$DOMAIN/api/" && echo && echo "Done: https://$DOMAIN/admin/"
