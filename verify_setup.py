import sys
import os

# Put current directory in python path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

print("=== CHECKING VIRTUAL ENVIRONMENT & IMPORTS ===")
try:
    import fastapi
    import uvicorn
    import sentence_transformers
    import pypdf
    import docx
    print("[SUCCESS] All required Python dependencies are installed and importable.")
except ImportError as e:
    print(f"[FAIL] Missing package: {e}")
    sys.exit(1)

print("\n=== CHECKING OLLAMA CONNECTION ===")
try:
    import requests
    response = requests.get("http://localhost:11434/api/tags", timeout=5)
    if response.status_code == 200:
        models = [m["name"] for m in response.json().get("models", [])]
        print(f"[SUCCESS] Connected to Ollama. Installed models: {', '.join(models)}")
        
        target_model = "llama3.1:8b"
        if any(target_model in m for m in models):
            print(f"[SUCCESS] '{target_model}' model is pulled and ready.")
        else:
            print(f"[WARNING] '{target_model}' not found in Ollama list. Please run: 'ollama pull {target_model}'")
    else:
        print(f"[FAIL] Ollama responded with status code: {response.status_code}")
except Exception as e:
    print(f"[FAIL] Could not connect to Ollama at http://localhost:11434. Error: {e}")
    print("Please make sure Ollama is running.")

print("\n=== PROJECT DIRECTORIES ===")
data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "legal_sources")
if os.path.exists(data_dir):
    files = os.listdir(data_dir)
    print(f"[INFO] Legal sources folder exists: {data_dir}")
    print(f"[INFO] Files found: {files if files else 'None (Place legal PDF/TXT files here)'}")
else:
    print(f"[WARNING] Legal sources folder does not exist yet. It will be created on server run.")

print("\n=== Verification Finished ===")
