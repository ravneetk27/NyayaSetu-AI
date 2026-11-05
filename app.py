import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
backend_path = str(BASE_DIR / "backend")
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Ensure 'app' package resolves to backend/app rather than this root file
sys.modules.pop('app', None)

# ZeroGPU protocol requirement for HF Spaces (works seamlessly on CPU or ZeroGPU)
def _zero_gpu_worker(text: str = "") -> str:
    """Satisfies ZeroGPU startup requirement for HF Spaces"""
    return text

try:
    import spaces
    zero_gpu_worker = spaces.GPU(_zero_gpu_worker)
except Exception:
    zero_gpu_worker = _zero_gpu_worker

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

# Build Gradio Blocks that hosts our custom web UI cleanly inside the HF Space iframe
with gr.Blocks(title="NyayaSetu AI", css=".gradio-container {max-width: 100% !important; padding: 0 !important; margin: 0 !important;} footer {display: none !important;}") as demo:
    # Hidden components hooked to zero_gpu_worker to satisfy HF ZeroGPU startup scan
    _z_in = gr.Textbox(visible=False, elem_id="zero_gpu_probe_in")
    _z_out = gr.Textbox(visible=False, elem_id="zero_gpu_probe_out")
    _z_btn = gr.Button(visible=False, elem_id="zero_gpu_probe_btn")
    _z_btn.click(zero_gpu_worker, inputs=[_z_in], outputs=[_z_out])

    gr.HTML('<iframe src="/web" style="width: 100vw; height: 98vh; border: none; margin: 0; padding: 0;"></iframe>')

# Mount Gradio at root "/" so Hugging Face Spaces healthcheck finds /config and stays healthy
app = gr.mount_gradio_app(fastapi_app, demo, path="/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7860))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
