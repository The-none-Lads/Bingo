# ---- Build stage ----
FROM node:26-alpine AS build
WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ .
RUN npm run build

# ---- Serve stage ----
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Copy build output
COPY --from=build /app/dist ./

# Copy entrypoint script
COPY frontend/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 80

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
