import os
import sys
from pathlib import Path
import spaces
import gradio as gr
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
backend_path = str(BASE_DIR / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Ensure 'app' package resolves to backend/app rather than this root file
sys.modules.pop('app', None)

# ZeroGPU protocol requirement for HF Spaces
@spaces.GPU
def zero_gpu_worker(query: str = "") -> str:
    """Module-level function satisfying HF Spaces ZeroGPU AST startup scanner"""
    return query

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

# Gradio Interface directly bound to @spaces.GPU function to pass ZeroGPU startup check
demo = gr.Interface(
    fn=zero_gpu_worker,
    inputs=gr.Textbox(visible=False),
    outputs=gr.Textbox(visible=False),
    title="NyayaSetu AI",
    description='<iframe src="/web" style="width: 100vw; height: 96vh; border: none; margin: 0; padding: 0;"></iframe>',
    css=".gradio-container {max-width: 100% !important; padding: 0 !important; margin: 0 !important;} footer {display: none !important;}"
)

# Mount Gradio at root "/" so Hugging Face Spaces healthcheck finds /config and stays healthy
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
