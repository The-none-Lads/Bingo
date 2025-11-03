# ---- Build stage ----
FROM node:25-alpine3.22 AS build
WORKDIR /app

# Install dependencies
COPY frontend/package*.json ./
RUN npm install

# Build the app
COPY frontend/ .
RUN npm run build

# ---- Serve stage ----
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Copy build output from previous stage
COPY --from=build /app/dist ./

# Expose port 80
EXPOSE 80

# Default Nginx command
CMD ["nginx", "-g", "daemon off;"]
