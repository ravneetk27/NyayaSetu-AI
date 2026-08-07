import requests
import time

url = "http://127.0.0.1:8000/api/analyze"
posh_payload = {
    "raw_text": "I am Priya Sharma, phone 9876543210. Since last month, my supervisor Raj Malhotra has been sending me inappropriate personal messages late at night and making uncomfortable remarks during meetings. This happened in Noida office. My colleague Amit Sen was present during one incident. Email me at priya@workplace.com."
}

log_file = "profile_direct_output.txt"

print("Starting profiling request...")
start_time = time.time()
try:
    resp = requests.post(url, json=posh_payload, timeout=120)
    end_time = time.time()
    result = f"Status Code: {resp.status_code}\nTime Taken: {end_time - start_time:.4f} seconds\n"
    if resp.status_code == 200:
        data = resp.json()
        result += f"Category: {data.get('classification', {}).get('category')}\n"
        result += f"Complainant: {data.get('extracted_facts', {}).get('complainant_name')}\n"
        result += f"Respondent: {data.get('extracted_facts', {}).get('respondent_name')}\n"
    else:
        result += f"Error: {resp.text}\n"
except Exception as e:
    result = f"Exception: {e}\n"

with open(log_file, "w", encoding="utf-8") as f:
    f.write(result)

print("Done profiling!")
