import time
import requests
import json
import sys

BASE_URL = "http://localhost:8000"
API_KEY = "apikey123"
AUTH_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
}

results = []

def record(name, endpoint, method, status_code, ok, duration_sec, details=""):
    results.append({
        "name": name,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "ok": ok,
        "duration": round(duration_sec, 3),
        "details": details
    })
    status_icon = "✅ PASS" if ok else "❌ FAIL"
    print(f"[{status_icon}] {method} {endpoint} -> {status_code} ({round(duration_sec, 3)}s): {details}")

# 1. Healthcheck
t0 = time.time()
r = requests.get(f"{BASE_URL}/health")
record("Health Check", "/health", "GET", r.status_code, r.status_code == 200, time.time() - t0, r.text)

# 2. Web UI Login Page
t0 = time.time()
r = requests.get(f"{BASE_URL}/login")
record("Web UI Login", "/login", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"{len(r.text)} bytes")

# 3. Models List
t0 = time.time()
r = requests.get(f"{BASE_URL}/v1/models", headers=AUTH_HEADERS)
data = r.json() if r.status_code == 200 else {}
models = [m.get("id") for m in data.get("data", [])]
record("Models List", "/v1/models", "GET", r.status_code, r.status_code == 200 and len(models) > 0, time.time() - t0, f"Models: {models}")

# 4. TTS Sync (Edge)
t0 = time.time()
r = requests.post(
    f"{BASE_URL}/v1/audio/speech",
    headers=AUTH_HEADERS,
    json={"model": "edge", "input": "Tes suara Edge TTS.", "voice": "id-ID-GadisNeural", "response_format": "mp3"}
)
record("TTS Sync (Edge)", "/v1/audio/speech", "POST", r.status_code, r.status_code == 200 and len(r.content) > 1000, time.time() - t0, f"Size: {len(r.content)} bytes")
sample_audio_edge = r.content

# 5. TTS Sync (Kokoro)
t0 = time.time()
r = requests.post(
    f"{BASE_URL}/v1/audio/speech",
    headers=AUTH_HEADERS,
    json={"model": "kokoro", "input": "Hello from Kokoro ONNX.", "voice": "af_heart", "response_format": "mp3"}
)
record("TTS Sync (Kokoro)", "/v1/audio/speech", "POST", r.status_code, r.status_code == 200 and len(r.content) > 1000, time.time() - t0, f"Size: {len(r.content)} bytes")

# 6. STT Sync (Whisper)
t0 = time.time()
files = {"file": ("test.mp3", sample_audio_edge, "audio/mpeg")}
data = {"model": "base", "language": "id"}
r = requests.post(f"{BASE_URL}/v1/audio/transcriptions", headers=AUTH_HEADERS, files=files, data=data)
res_text = r.json().get("text", "") if r.status_code == 200 else ""
record("STT Sync (Whisper)", "/v1/audio/transcriptions", "POST", r.status_code, r.status_code == 200 and len(res_text) > 0, time.time() - t0, f"Transkripsi: '{res_text}'")

# 7. Async Job Queue - Speech (Enqueue)
t0 = time.time()
r = requests.post(
    f"{BASE_URL}/v1/jobs/speech",
    headers=AUTH_HEADERS,
    json={"model": "edge", "input": "Tes antrian async job.", "voice": "id-ID-GadisNeural", "response_format": "mp3"}
)
job_info = r.json() if r.status_code in (200, 202) else {}
job_id = job_info.get("job_id")
record("Async Job Speech Enqueue", "/v1/jobs/speech", "POST", r.status_code, r.status_code in (200, 202) and bool(job_id), time.time() - t0, f"Job ID: {job_id}")

# 8. Async Job Status Polling
tts_job_done = False
if job_id:
    for _ in range(30):
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/v1/jobs/{job_id}", headers=AUTH_HEADERS)
        st = r.json().get("status")
        if st in ("completed", "failed"):
            tts_job_done = (st == "completed")
            record("Async Job Status Polling", f"/v1/jobs/{job_id}", "GET", r.status_code, tts_job_done, time.time() - t0, f"Final Status: {st}")
            break
        time.sleep(0.5)

# 9. Async Job Result Download
if job_id and tts_job_done:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/v1/jobs/{job_id}/result", headers=AUTH_HEADERS)
    record("Async Job Result Download", f"/v1/jobs/{job_id}/result", "GET", r.status_code, r.status_code == 200 and len(r.content) > 1000, time.time() - t0, f"Result size: {len(r.content)} bytes")

# 10. Async Job Queue - Transcription (Enqueue)
t0 = time.time()
files = {"file": ("test.mp3", sample_audio_edge, "audio/mpeg")}
data = {"model": "base", "language": "id"}
r = requests.post(f"{BASE_URL}/v1/jobs/transcriptions", headers=AUTH_HEADERS, files=files, data=data)
stt_job_info = r.json() if r.status_code in (200, 202) else {}
stt_job_id = stt_job_info.get("job_id")
record("Async Job STT Enqueue", "/v1/jobs/transcriptions", "POST", r.status_code, r.status_code in (200, 202) and bool(stt_job_id), time.time() - t0, f"Job ID: {stt_job_id}")

# 11. Async Job STT Status Polling
stt_job_done = False
if stt_job_id:
    for _ in range(30):
        t0 = time.time()
        r = requests.get(f"{BASE_URL}/v1/jobs/{stt_job_id}", headers=AUTH_HEADERS)
        st = r.json().get("status")
        if st in ("completed", "failed"):
            stt_job_done = (st == "completed")
            record("Async Job STT Status Polling", f"/v1/jobs/{stt_job_id}", "GET", r.status_code, stt_job_done, time.time() - t0, f"Final Status: {st}")
            break
        time.sleep(0.5)

# 12. Async Job STT Result Download
if stt_job_id and stt_job_done:
    t0 = time.time()
    r = requests.get(f"{BASE_URL}/v1/jobs/{stt_job_id}/result", headers=AUTH_HEADERS)
    res_data = r.json() if r.status_code == 200 else {}
    record("Async Job STT Result Download", f"/v1/jobs/{stt_job_id}/result", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"STT Result: {res_data.get('text', '')}")

# 13. List Jobs
t0 = time.time()
r = requests.get(f"{BASE_URL}/v1/jobs", headers=AUTH_HEADERS)
jobs_list = r.json() if r.status_code == 200 else {}
record("List Jobs", "/v1/jobs", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"Total Jobs: {len(jobs_list.get('jobs', []))}")

# 14. Studio System Info
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/system", headers=AUTH_HEADERS)
sys_info = r.json() if r.status_code == 200 else {}
record("Studio System Info", "/api/system", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"OS: {sys_info.get('hardware', {}).get('os')}, Chip: {sys_info.get('hardware', {}).get('chip')}")

# 15. Studio Engines
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/engines", headers=AUTH_HEADERS)
eng_info = r.json() if r.status_code == 200 else []
record("Studio Engines List", "/api/engines", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"{len(eng_info)} engines available")

# 16. Studio README
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/readme", headers=AUTH_HEADERS)
readme_data = r.json() if r.status_code == 200 else {}
content_len = len(readme_data.get("content", ""))
record("Studio README Doc", "/api/readme", "GET", r.status_code, r.status_code == 200 and content_len > 0, time.time() - t0, f"README length: {content_len} chars")

# 17. Studio History
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/history", headers=AUTH_HEADERS)
hist_data = r.json() if r.status_code == 200 else {}
record("Studio History", "/api/history", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"Total Generations: {hist_data.get('total', 0)}")

# 18. Studio Voice Clones
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/clones", headers=AUTH_HEADERS)
clones_data = r.json() if r.status_code == 200 else []
record("Studio Voice Clones", "/api/clones", "GET", r.status_code, r.status_code == 200, time.time() - t0, f"{len(clones_data)} clones stored")

# 19. Sample Audio Voice
t0 = time.time()
r = requests.get(f"{BASE_URL}/api/voices/sample?engine=edge&voice=id-ID-GadisNeural", headers=AUTH_HEADERS)
record("Studio Voice Sample", "/api/voices/sample", "GET", r.status_code, r.status_code == 200 and len(r.content) > 1000, time.time() - t0, f"Audio sample size: {len(r.content)} bytes")

# Save report
with open("/Volumes/mydata/Users/Adsmedia/Development/Apps/tts-local/data/api_test_results.json", "w") as f:
    json.dump(results, f, indent=2)

passed = sum(1 for x in results if x["ok"])
total = len(results)
print(f"\n==========================================")
print(f"TEST SUMMARY: {passed}/{total} Passed ({round(passed/total*100, 1)}%)")
print(f"==========================================")
