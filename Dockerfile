# ── Stage: base image ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# Keeps Python from generating .pyc files and enables unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    HOME=/home/user

WORKDIR /app

# Create a non-root user (UID 1000 is required by Hugging Face Spaces)
RUN useradd -m -u 1000 user && \
    mkdir -p /home/user/.cache && \
    chown -R user:user /home/user

# ── Layer 1: Install dependencies (cached unless requirements.txt changes) ─────
COPY backend/requirements.txt ./backend/requirements.txt
# Pre-install CPU-only PyTorch first to avoid downloading 2GB+ CUDA wheels
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r ./backend/requirements.txt

# ── Layer 2: Copy application source ──────────────────────────────────────────
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user frontend/ ./frontend/
COPY --chown=user:user data/     ./data/

RUN chown -R user:user /app

# Switch to non-root user
USER user

# Run from backend/ so run.py resolves paths correctly
WORKDIR /app/backend

EXPOSE 7860

# run.py handles auto-ingestion + starts uvicorn on $PORT
CMD ["python", "run.py"]

