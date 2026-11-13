# syntax=docker/dockerfile:1
# Build context: repository root.  Targets: "web" (Nginx + admin UI) and "backend" (FastAPI API).

FROM node:20-bookworm-slim AS frontend-build
WORKDIR /src/frontend
ARG REACT_APP_BACKEND_URL=https://propertysavailable.com
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL} \
    PUBLIC_URL=/admin \
    GENERATE_SOURCEMAP=false \
    CI=false
COPY frontend/package.json frontend/yarn.lock ./
RUN yarn install --frozen-lockfile --network-timeout 600000
COPY frontend/ ./
RUN rm -f .env && yarn build

FROM nginx:1.27-alpine AS web
RUN rm -f /etc/nginx/conf.d/default.conf && mkdir -p /var/www/certbot
COPY deploy/nginx/propertysavailable.conf /etc/nginx/conf.d/propertysavailable.conf
COPY --from=frontend-build /src/frontend/build /usr/share/nginx/html/admin
EXPOSE 80 443

FROM python:3.11-slim AS backend
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY deploy/requirements.prod.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY backend/*.py ./
RUN useradd --system --uid 10001 app && chown -R app /app
USER app
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/api/')" || exit 1
# Single worker on purpose: audit-log hash chain uses an in-process lock.
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
