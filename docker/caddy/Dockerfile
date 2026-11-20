# Web container: builds the SPA, then serves it with Caddy (automatic HTTPS) and proxies /api, /ws and /admin.
FROM node:22-slim AS build
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM caddy:2
COPY --from=build /app/dist /srv
COPY docker/caddy/Caddyfile /etc/caddy/Caddyfile
