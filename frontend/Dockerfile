# FixitLab Frontend — Multi-stage production build
# Stage 1: Build the React app
FROM node:20-alpine AS builder

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --production=false
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Custom nginx config for SPA routing
COPY --from=builder /app/dist /usr/share/nginx/html

RUN cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name _;

    root /usr/share/nginx/html;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml text/javascript image/svg+xml;

    # Cache static assets aggressively
    location ~* \.(js|css|png|jpg|jpeg|gif|svg|ico|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # ── Self-hosted runtimes: Pyodide + MediaPipe (~28MB, version-pinned) ──
    # Kept in sync with Dockerfile.prod, which serves the same dist/. `^~` beats
    # the regex above so the .wasm/.zip/.tflite siblings get the long cache too,
    # not just the .js entry points.
    location ^~ /pyodide/ {
        expires 1y;
        add_header Cache-Control "public, immutable" always;
        access_log off;
    }

    location ^~ /vendor/ {
        expires 1y;
        add_header Cache-Control "public, immutable" always;
        access_log off;
    }

    # SPA fallback — all routes serve index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
