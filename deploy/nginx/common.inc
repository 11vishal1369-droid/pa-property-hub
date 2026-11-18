# Shared by the website and admin server blocks.
ssl_protocols TLSv1.2 TLSv1.3;
ssl_session_cache shared:SSL:10m;

add_header Strict-Transport-Security "max-age=31536000" always;
add_header X-Content-Type-Options nosniff always;
add_header X-Frame-Options SAMEORIGIN always;
add_header Referrer-Policy strict-origin-when-cross-origin always;

client_max_body_size 20m;
gzip on;
gzip_types text/css application/javascript application/json image/svg+xml;

location /.well-known/acme-challenge/ { root /var/www/certbot; }

location /static/ {
    root /usr/share/nginx/html;
    expires 1y;
    add_header Cache-Control "public, immutable";
}

location /site/ {
    root /usr/share/nginx/html;
    expires 7d;
}

# Admin backend API (also used by the Owner/Tenant apps).
location /api/ {
    proxy_pass http://backend:8001;
    include /etc/nginx/conf.d/proxy.inc;
}
