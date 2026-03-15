# ═══════════════════════════════════════════════════════
#  Stock Portfolio Dashboard - Multi-stage Docker Build
#  Works on ARM64 (Raspberry Pi 5) and x86_64
# ═══════════════════════════════════════════════════════

# ── Stage 1: Build Frontend ───────────────────────────
FROM node:20-slim AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python Backend ───────────────────────────
FROM python:3.12-slim

# System deps for pdfplumber (pdfminer) and health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code
COPY backend/app/ ./backend/app/
COPY backend/data/ ./backend/data/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Create dumps directory (mount point for persistent data)
RUN mkdir -p /app/backend/dumps

# Non-root user for security
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 9999

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -sf http://localhost:9999/health || exit 1

WORKDIR /app/backend

# Graceful shutdown — uvicorn handles SIGTERM
STOPSIGNAL SIGTERM

CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "9999", "--timeout-graceful-shutdown", "25"]
