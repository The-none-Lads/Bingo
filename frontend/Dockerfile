# ---- Build stage ----
FROM node:25-alpine3.22 AS build
WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .
RUN npm run build

# ---- Serve stage ----
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Set environment variables for config
ENV apiBaseUrl=/ \
    wsBaseUrl=localhost:8000/ws \
    pollInterval=20000 \
    cardFetchInterval=300000 \
    gameIdDefault=demo \
    enableCelebration=true \
    confettiDuration=5000

# Copy build output
COPY --from=build /app/dist ./

# Copy entrypoint script
COPY frontend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
