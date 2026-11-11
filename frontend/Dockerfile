# ---- Build stage ----
FROM node:26-alpine AS build
WORKDIR /app

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ .
RUN npm run build

# ---- Serve stage ----
FROM nginxinc/nginx-unprivileged:alpine
WORKDIR /usr/share/nginx/html

# Copy build output
COPY --from=build --chown=101:101 /app/dist/ ./

# Copy entrypoint script
COPY --chown=101:101 --chmod=755 frontend/entrypoint.sh /entrypoint.sh
USER 101:101

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
