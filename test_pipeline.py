import requests
import time
import sys
import subprocess
import os
import traceback

# Put current directory in python path for direct imports in test script
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend'))

# Reconfigure standard output streams to handle Unicode on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

server_already_running = False
try:
    resp = requests.get("http://127.0.0.1:8000/docs", timeout=2)
    if resp.status_code == 200:
        server_already_running = True
        print("[INFO] Server is already running on port 8000. Skipping server startup.")
except Exception:
    pass

if not server_already_running:
    print("=== STARTING BACKEND FOR TESTING ===")
    # Use files instead of PIPEs to avoid Windows buffer deadlock
    out_file = open("test_server_out.log", "w", encoding="utf-8")
    err_file = open("test_server_err.log", "w", encoding="utf-8")

    server_process = subprocess.Popen(
        [sys.executable, "backend/run.py"],
        stdout=out_file,
        stderr=err_file,
        text=True
    )

    # Wait for server to start
    print("Waiting for server to start (15s)...")
    for i in range(15):
        print(f"Waiting... {15-i}s remaining")
        time.sleep(1)
        if server_process.poll() is not None:
            print(f"[FAIL] Server exited early with code {server_process.returncode}")
            out_file.close()
            err_file.close()
            with open("test_server_err.log", "r", encoding="utf-8") as f:
                print("STDERR Logs:")
                print(f.read())
            sys.exit(1)

url_base = "http://127.0.0.1:8000"

try:
    # 1. Test Anonymizer Directly
    print("\n--- Testing Anonymizer Directly ---")
    from app.core.anonymizer import Anonymizer
    anon = Anonymizer()
    sample_pii_text = "My email is priya@workplace.com and phone is 9876543210."
    anon_text, pii_map = anon.anonymize(sample_pii_text)
    print(f"Original: {sample_pii_text}")
    print(f"Anonymized: {anon_text}")
    print(f"Map: {pii_map}")
    assert "[EMAIL_1]" in anon_text
    assert "[PHONE_1]" in anon_text
    restored_text = anon.deanonymize(anon_text, pii_map)
    print(f"Restored: {restored_text}")
    assert restored_text == sample_pii_text
    print("[SUCCESS] Direct Anonymizer unit test passed.")

    # 2. Ingest Documents
    print("\n--- Testing Document Ingestion ---")
    resp = requests.post(f"{url_base}/api/ingest")
    print(f"Ingest Status Code: {resp.status_code}")
    print(f"Ingest Response: {resp.json()}")
    assert resp.status_code == 200
    assert resp.json()["total_chunks"] > 0
    print("[SUCCESS] Ingestion test passed.")

    # 3. Test POSH Narrative
    print("\n--- Testing POSH Incident Analysis & Templates ---")
    posh_payload = {
        "raw_text": "I am Priya Sharma, phone 9876543210. Since last month, my supervisor Raj Malhotra has been sending me inappropriate personal messages late at night and making uncomfortable remarks during meetings. This happened in Noida office. My colleague Amit Sen was present during one incident. Email me at priya@workplace.com."
    }
    resp = requests.post(f"{url_base}/api/analyze", json=posh_payload)
    print(f"POSH Status Code: {resp.status_code}")
    data = resp.json()
    print(f"Classification: {data['classification']}")
    print(f"Extracted Facts: {data['extracted_facts']}")
    print(f"Mandatory Alert: {data['mandatory_report_alert']}")
    print(f"Draft Addressed To: {data['draft']['addressed_to']}")
    
    assert data["classification"]["category"] == "POSH"
    assert data["mandatory_report_alert"] is False
    assert "Priya Sharma" in data["draft"]["draft_text"] or "Priya Sharma" in str(data["extracted_facts"])
    
    print("\n--- GENERATED DRAFT TEXT ---")
    print(data["draft"]["draft_text"])
    print("----------------------------")
    
    # Assert that the draft follows the POSH template structure (using loose substring matches to account for model variations)
    assert "POSH" in data["draft"]["draft_text"] or "Sexual Harassment" in data["draft"]["draft_text"]
    assert "Complainant Details" in data["draft"]["draft_text"]
    assert "Respondent" in data["draft"]["draft_text"] or "Accused" in data["draft"]["draft_text"]
    assert "Details of Incident" in data["draft"]["draft_text"] or "Incident Details" in data["draft"]["draft_text"]
    print("[SUCCESS] POSH analysis and template matching passed.")

    # 4. Test POCSO Narrative
    print("\n--- Testing POCSO Incident Analysis & Templates ---")
    pocso_payload = {
        "raw_text": "A child named Aarav, age 12, who is a student at Sunshine High School, was touched inappropriately by the school bus driver Suresh Kumar on July 10 near the school parking lot. Another student Rahul saw it happen."
    }
    resp = requests.post(f"{url_base}/api/analyze", json=pocso_payload)
    print(f"POCSO Status Code: {resp.status_code}")
    data = resp.json()
    print(f"Classification: {data['classification']}")
    print(f"Extracted Facts: {data['extracted_facts']}")
    print(f"Mandatory Alert: {data['mandatory_report_alert']}")
    print(f"Draft Addressed To: {data['draft']['addressed_to']}")
    
    assert data["classification"]["category"] == "POCSO" or data["classification"]["minor_involved"] is True
    assert data["mandatory_report_alert"] is True
    assert "Police" in data["draft"]["addressed_to"] or "SJPU" in data["draft"]["addressed_to"]
    
    print("\n--- GENERATED POCSO DRAFT TEXT ---")
    print(data["draft"]["draft_text"])
    print("----------------------------------")

    # Assert that the draft follows the POCSO template structure
    assert "POCSO" in data["draft"]["draft_text"]
    assert "Mandatory" in data["draft"]["draft_text"] or "MANDATORY" in data["draft"]["draft_text"]
    print("[SUCCESS] POCSO analysis and template matching passed.")

    print("\n=== ALL PIPELINE TESTS PASSED ===")
    
except Exception as e:
    print(f"\n[FAIL] Test pipeline failed: {e}")
    traceback.print_exc()
    # Print server log if available
    try:
        out_file.close()
        err_file.close()
        with open("test_server_err.log", "r", encoding="utf-8") as f:
            print("\n--- SERVER ERR LOG ---")
            print(f.read())
    except:
        pass
    sys.exit(1)
finally:
    if not server_already_running:
        print("Stopping test server...")
        try:
            server_process.terminate()
            server_process.wait()
        except:
            pass
        try:
            out_file.close()
            err_file.close()
        except:
            pass
