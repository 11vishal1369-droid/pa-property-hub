#!/bin/sh
# Use the Let's Encrypt certificate when present; otherwise a temporary self-signed one so Nginx can start
# (needed for the first `docker compose up` before deploy.sh requests the real certificate).
set -e
LE=/etc/letsencrypt/live/propertysavailable.com
OUT=/etc/nginx/certs
mkdir -p "$OUT"
if [ -f "$LE/fullchain.pem" ] && [ -f "$LE/privkey.pem" ]; then
  ln -sf "$LE/fullchain.pem" "$OUT/fullchain.pem"
  ln -sf "$LE/privkey.pem" "$OUT/privkey.pem"
  echo "certs: using Let's Encrypt certificate"
else
  rm -f "$OUT/fullchain.pem" "$OUT/privkey.pem"
  openssl req -x509 -nodes -newkey rsa:2048 -days 7 -subj "/CN=propertysavailable.com" \
    -keyout "$OUT/privkey.pem" -out "$OUT/fullchain.pem" >/dev/null 2>&1
  echo "certs: Let's Encrypt certificate not found, using temporary self-signed certificate"
fi
