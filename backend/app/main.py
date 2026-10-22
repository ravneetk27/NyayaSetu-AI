import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pathlib import Path
from app.api.endpoints import router as api_router
from app.config import BASE_DIR

app = FastAPI(
    title="PoSH/POCSO Legal Advisory AI Agent MVP",
    description="Local AI advisory agent for legal complaint drafting.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix="/api")

# ── Health check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["ops"])
def health_check():
    """Liveness probe — used by Docker, Compose healthcheck, and CI smoke tests."""
    return JSONResponse(status_code=200, content={"status": "ok", "service": "NyayaSetu AI"})


# Verify frontend directory exists before mounting
frontend_path = BASE_DIR / "frontend"
frontend_path.mkdir(parents=True, exist_ok=True)

# Mount static files at root
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
