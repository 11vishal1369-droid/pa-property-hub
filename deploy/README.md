# Propertys Available: aaPanel VPS deployment (Ubuntu 22.04, 201.18.206.131)

aaPanel's Nginx (on the host) handles the domains and HTTPS. Docker runs everything else; there is no Nginx container.

| Container | Host port (127.0.0.1) | Serves |
|---|---|---|
| `website` | 3000 | Main website: Home, Terms & Conditions, Privacy Policy, Refund Policy, Contact Us, editor at `/webcontent` |
| `admin` | 3001 | Admin panel (at `/admin/`; `/` redirects there) |
| `backend` | 5000 | Backend API `/api/` (admin panel + Owner/Tenant apps) |
| `webcontent` | 5001 | Website content service `/webcontent-api/` |
| `mongo` | not exposed | Database, reachable only inside Docker |

Ports bind to `127.0.0.1` so they are only reachable from aaPanel's Nginx on the same server. Set `BIND_IP=0.0.0.0` in `.env` only if you need them open.

## Deploy
1. DNS: A records for `propertysavailable.com`, `www.propertysavailable.com`, `admin.propertysavailable.com` → `201.18.206.131`.
2. Put the repository at `/opt/propertysavailable`.
3. `cd /opt/propertysavailable/deploy && cp .env.example .env` and fill in every value.
4. `sudo ./deploy.sh` (installs Docker if missing, then `docker compose up -d --build`, then checks all four ports).
   Later updates: `git pull && docker compose up -d --build`.
5. Set up the two sites in aaPanel as below, and enable SSL (Let's Encrypt) for each in aaPanel.

## aaPanel reverse proxy settings

### Site 1: propertysavailable.com (add www.propertysavailable.com as an alias)
| Proxy name | Proxy directory (path) | Target URL |
|---|---|---|
| api | `/api/` | `http://127.0.0.1:5000` |
| webcontent | `/webcontent-api/` | `http://127.0.0.1:5001` |
| website | `/` | `http://127.0.0.1:3000` |

Send domain / Host header: `$host`. Optional: redirect `/admin` to `https://admin.propertysavailable.com/admin/`.

### Site 2: admin.propertysavailable.com
| Proxy name | Proxy directory (path) | Target URL |
|---|---|---|
| api | `/api/` | `http://127.0.0.1:5000` |
| admin | `/` | `http://127.0.0.1:3001` |

Opening `https://admin.propertysavailable.com/` redirects to `/admin/` (the panel's address).

Target URLs have no trailing path, so the full path (`/api/...`, `/admin/...`) is passed through unchanged.

## Read before going live
- First start seeds sample admin data only if Firebase is not configured. If it does, deactivate the 6 staff logins (`Staff@123`).
- `AADHAAR_ENC_KEY` must match the key used for any data you migrate in. Back it up.
- Editor login (`WEB_EDITOR_EMAIL` / `WEB_EDITOR_PASSWORD`) is created on first start only.
- One worker per Python service is required (audit-log hash chain).
- Backups: `docker compose exec mongo mongodump --archive > backup.archive`
