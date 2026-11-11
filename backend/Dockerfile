FROM python:3.15-slim AS backend
WORKDIR /app

# Copy requirements first (better for caching)
COPY backend/requirements.txt .

# Install backend dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend code
COPY backend/ .

# Create non-root user, a writable data directory for the persistent
# card store (backend/storage/db.py), and set permissions
RUN useradd -m -u 1001 appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

# Mount a volume at /app/data (see docker-compose.yml / the Kubernetes
# PersistentVolumeClaim) so generated cards survive a container restart
# or recreation, not just an in-process restart.
VOLUME ["/app/data"]

# Expose FastAPI port
EXPOSE 8000

# Liveness check does not depend on external services.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

