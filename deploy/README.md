# PA Super Admin: VPS deployment package (Ubuntu 22.04)

Serves the admin panel at `https://propertysavailable.com/admin/` and the admin API at `https://propertysavailable.com/api/`.

## Files
| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage. Target `web`: Nginx 1.27 + React build (built with `PUBLIC_URL=/admin`). Target `backend`: FastAPI on Python 3.11 (single worker). |
| `docker-compose.yml` | Services `mongo` (data in volume `mongo-data`), `backend`, `web` (ports 80/443). |
| `nginx/propertysavailable.conf` | HTTP→HTTPS, `/admin/` SPA routing, `/api/` proxy to backend, Let's Encrypt webroot. |
| `deploy.sh` | Installs Docker, pulls images (or builds from source), gets a TLS certificate, starts containers, sets up renewal. |
| `requirements.prod.txt` | Only the backend's runtime packages (the dev `requirements.txt` has environment-only packages). |
| `.env.example` | Every variable the backend needs. |

## Deploy
1. Point the DNS A records for `propertysavailable.com` and `www.propertysavailable.com` at the VPS. Open ports 80 and 443.
2. Copy the whole repository to the VPS, e.g. `/opt/pa-admin`.
3. `cd /opt/pa-admin/deploy && cp .env.example .env`, then fill in every value.
4. `sudo CERT_EMAIL=you@example.com ./deploy.sh`

To use prebuilt images instead of building on the VPS, build and push both targets, then set `BACKEND_IMAGE` and `WEB_IMAGE` in `.env`:
```
docker build -f deploy/Dockerfile --target backend -t <registry>/pa-admin-backend:1.0 .
docker build -f deploy/Dockerfile --target web --build-arg REACT_APP_BACKEND_URL=https://propertysavailable.com -t <registry>/pa-admin-web:1.0 .
```

## Read before going live
- **`/api` conflict:** the mobile app's backend is also said to live at `propertysavailable.com/api`. Only one service can own that path. If both run, move one (for example, serve the admin API under a different path or subdomain) before deploying.
- **Main site:** `location /` returns 404. If the existing propertysavailable.com website runs on this VPS, point that block at it.
- **First start seeds sample data** when the database is empty. That includes 6 staff logins with the shared password `Staff@123`. Deactivate those or change their passwords right after the first login.
- **`AADHAAR_ENC_KEY`** must match the key used for any data you migrate in. Back it up; without it, stored Aadhaar numbers can't be decrypted.
- **Single backend worker** is required: the audit-log hash chain relies on an in-process lock.
- **Backups:** `docker compose exec mongo mongodump --archive > backup.archive`
