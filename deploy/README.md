# Propertys Available: VPS deployment (Ubuntu 22.04)

One project, one Docker Compose stack, one VPS (`201.18.206.131`):

| Address | Serves |
|---|---|
| `https://propertysavailable.com/` (and `www.` → redirects to apex) | Main website: Home, Terms & Conditions, Privacy Policy, Refund Policy, Contact Us, and the content editor at `/webcontent` |
| `https://admin.propertysavailable.com/` | Admin panel (opens at `/admin/`) |
| `/api/` on both hosts | Admin backend API (also used by the Owner/Tenant apps) |
| `/webcontent-api/` | Website content service used by the website and `/webcontent` editor |

`propertysavailable.com/admin/...` redirects to `admin.propertysavailable.com/admin/...`.

## Files
| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage. `web`: Nginx 1.27 + one React build (website + admin panel). `backend`: admin FastAPI. `webcontent`: website content service. |
| `docker-compose.yml` | Services `mongo` (volume `mongo-data`), `backend`, `webcontent`, `web` (ports 80/443). |
| `nginx/propertysavailable.conf` | Host routing above, HTTP→HTTPS, www→apex. Uses `common.inc` and `proxy.inc`. |
| `nginx/20-certs.sh` | Uses the Let's Encrypt certificate if present; otherwise a temporary self-signed one so Nginx always starts. |
| `deploy.sh` | Installs Docker, runs `docker compose up -d --build`, requests one certificate for all three names, sets up daily renewal. |
| `requirements.prod.txt` | Runtime packages for both Python services. |
| `.env.example` | Every variable the services need. |

## Deploy
1. DNS: A records for `propertysavailable.com`, `www.propertysavailable.com` and `admin.propertysavailable.com` → `201.18.206.131`. Open ports 80 and 443.
2. Put the repository at `/opt/propertysavailable` (e.g. `git clone <repo> /opt/propertysavailable`).
3. `cd /opt/propertysavailable/deploy && cp .env.example .env`, then fill in every value.
4. First time: `sudo CERT_EMAIL=you@example.com ./deploy.sh` (gets the HTTPS certificate).
5. Later updates: `git pull && docker compose up -d --build` from `/opt/propertysavailable/deploy` starts/rebuilds everything.

## Read before going live
- **First start seeds sample admin data only if Firebase is not configured.** If it does, deactivate the 6 staff logins (`Staff@123`) right away.
- **`AADHAAR_ENC_KEY`** must match the key used for any data you migrate in. Back it up.
- **Editor login** (`WEB_EDITOR_EMAIL` / `WEB_EDITOR_PASSWORD`) is created on first start only; change the password inside `/webcontent` afterwards.
- **Single worker** per Python service is required (audit-log hash chain uses an in-process lock).
- **Backups:** `docker compose exec mongo mongodump --archive > backup.archive`
