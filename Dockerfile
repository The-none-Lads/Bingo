# ---- Frontend build stage ----
FROM node:latest AS frontend-build
WORKDIR /app/frontend

# Install and build React
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ---- Backend stage ----
FROM python:3.13-slim AS backend
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Copy built frontend into backend's static folder
COPY --from=frontend-build /app/frontend/build ./static

# Expose FastAPI port
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
