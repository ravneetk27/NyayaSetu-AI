import uvicorn
import os
import sys

# Ensure backend directory is in the python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import HOST, PORT

def auto_ingest():
    """
    On first boot (e.g. on Render), if the vector DB is missing but
    legal source files are present, run ingestion automatically so the
    RAG search works without a manual /api/ingest call.
    """
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


if __name__ == "__main__":
    auto_ingest()
    print(f"Starting NyayaSetu AI server on http://{HOST}:{PORT}...")
    reload_flag = os.getenv("ENV", "production").lower() == "development"
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=reload_flag)
