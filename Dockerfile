# ── Stage: base image ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# Keeps Python from generating .pyc files and enables stdout/stderr logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Layer 1: Install dependencies (cached unless requirements.txt changes) ─────
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# ── Layer 2: Copy application source ──────────────────────────────────────────
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY data/     ./data/

# Run from backend/ so run.py resolves paths correctly
WORKDIR /app/backend

EXPOSE 8000

# run.py handles auto-ingestion + starts uvicorn
CMD ["python", "run.py"]
