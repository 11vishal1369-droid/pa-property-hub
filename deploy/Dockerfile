# syntax=docker/dockerfile:1
# Build context: repository root.
# Targets: "web" (Nginx + website + admin UI), "backend" (admin FastAPI /api), "webcontent" (website content service).

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /src/frontend
# Admin panel API calls go to the admin subdomain (same origin as the panel).
ARG REACT_APP_BACKEND_URL=https://admin.propertysavailable.com
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL} \
    GENERATE_SOURCEMAP=false \
    CI=false
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY frontend/ ./
RUN rm -f .env src/setupProxy.js && yarn build

FROM nginx:1.27-alpine AS web
RUN apk add --no-cache openssl && rm -f /etc/nginx/conf.d/default.conf && mkdir -p /var/www/certbot /etc/nginx/certs
COPY deploy/nginx/propertysavailable.conf deploy/nginx/common.inc deploy/nginx/proxy.inc /etc/nginx/conf.d/
COPY deploy/nginx/20-certs.sh /docker-entrypoint.d/20-certs.sh
RUN chmod +x /docker-entrypoint.d/20-certs.sh
COPY --from=frontend-build /src/frontend/build /usr/share/nginx/html
EXPOSE 80 443

FROM python:3.11-slim AS python-base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY deploy/requirements.prod.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && useradd --system --uid 10001 app

FROM python-base AS backend
WORKDIR /app/backend
COPY backend/*.py ./
RUN chown -R app /app
USER app
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/api/')" || exit 1
# Single worker on purpose: audit-log hash chain uses an in-process lock.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]

FROM python-base AS webcontent
WORKDIR /app/webcontent
COPY webcontent/server.py webcontent/default_content.json ./
RUN chown -R app /app
USER app
EXPOSE 8002
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8002/webcontent-api/')" || exit 1
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
