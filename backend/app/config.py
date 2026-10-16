import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
LEGAL_SOURCES_DIR = DATA_DIR / "legal_sources"

# Ensure directories exist
LEGAL_SOURCES_DIR.mkdir(parents=True, exist_ok=True)

# Groq API Config (replaces local Ollama)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# llama-3.1-8b-instant: free, fast, great for legal text on Groq
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# Embedding Config
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

# App Config
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

