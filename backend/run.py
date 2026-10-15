import uvicorn
import os
import sys

# Ensure backend directory is in the python path
# Reload v2 triggered for POSH & POCSO Legal Advisory AI Agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import HOST, PORT

if __name__ == "__main__":
    print(f"Starting server on http://{HOST}:{PORT}...")
    reload_flag = os.getenv("ENV", "production").lower() == "development"
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=reload_flag)

