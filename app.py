import sys
import os
from pathlib import Path

# Ensure backend directory is in the python path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "backend"))

# Auto-ingest vector DB if needed
try:
    from app.core.rag import LegalRAG
    rag = LegalRAG()
    if not rag.chunks:
        print("Vector DB empty — running auto-ingestion of legal sources...")
        processed, total = rag.ingest_documents()
        print(f"Auto-ingestion complete: {len(processed)} files, {total} chunks.")
    else:
        print(f"Vector DB ready: {len(rag.chunks)} chunks loaded.")
except Exception as e:
    print(f"[WARN] Auto-ingestion skipped: {e}")

from app.main import app as fastapi_app
import gradio as gr
import uvicorn

# Define Gradio interface mounted alongside FastAPI
with gr.Blocks(title="NyayaSetu AI") as demo:
    gr.Markdown("# ⚖️ NyayaSetu AI")
    gr.Markdown("Interactive legal advisory engine. The web portal is active at `/`.")

# Mount Gradio app onto FastAPI at /gradio
app = gr.mount_gradio_app(fastapi_app, demo, path="/gradio")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"Starting server on port {port}...")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
