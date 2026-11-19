# LocalTTS — API Documentation

LocalTTS menyediakan endpoint **OpenAI-compatible** (`/v1/*`) serta endpoint **Studio & Management** (`/api/*`).

---

## 1. Autentikasi API (`.env`)

Keamanan API dikendalikan melalui environment variable `API_KEY`:

- **Jika `API_KEY` kosong (`API_KEY=`):** Semua endpoint `/v1/*` terbuka tanpa header autentikasi.
- **Jika `API_KEY` diisi (misal `API_KEY=sk-rahasia`):** Kirim salah satu header berikut di setiap request:
  - `Authorization: Bearer sk-rahasia`
  - `X-API-Key: sk-rahasia` (atau nama header kustom dari `API_KEY_HEADER`)

> Endpoint `/api/*` dilindungi oleh session cookie UI (`AUTH_USERNAME` & `AUTH_PASSWORD` di `.env`).

---

## 2. OpenAI-Compatible Endpoints

### `GET /v1/models`
Menampilkan daftar engine/model yang tersedia di server.

```bash
curl http://localhost:8000/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### `POST /v1/audio/speech` (Text-to-Speech)
Mengubah teks menjadi file audio (`mp3`, `wav`, `opus`, `flac`).

**Request Body (JSON):**
| Field | Type | Default | Keterangan |
| :--- | :--- | :--- | :--- |
| `model` | string | `"kokoro"` | `kokoro`, `edge`, `omnivoice`, `qwen3` (atau alias `tts-1`, `edge-tts`, `qwen3-tts`) |
| `input` | string | *(wajib)* | Teks yang akan diubah menjadi suara |
| `voice` | string | `"af_heart"` | ID suara (misal `af_heart`, `id-ID-GadisNeural`, `id_female`, `Vivian`) |
| `response_format` | string | `"mp3"` | `mp3`, `wav`, `opus`, `flac` |
| `speed` | float | `1.0` | Kecepatan bicara (`0.25` – `4.0`) |
| `language` | string | `"en-us"` | `en-us`, `en-gb`, `en`, `id` |
| `instruct` | string | `""` | Prompt gaya suara (khusus `omnivoice` / `qwen3`) |

**Contoh `curl` (Bahasa Indonesia via Edge-TTS):**
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "edge",
    "input": "Halo, selamat datang di layanan text to speech lokal.",
    "voice": "id-ID-GadisNeural",
    "language": "id",
    "response_format": "mp3"
  }' \
  --output hasil.mp3
```

**Contoh Python (`requests` & OpenAI SDK):**
```python
import requests

res = requests.post(
    "http://localhost:8000/v1/audio/speech",
    headers={"Authorization": "Bearer YOUR_API_KEY"},
    json={
        "model": "edge",
        "input": "Halo dari LocalTTS!",
        "voice": "id-ID-GadisNeural",
        "language": "id",
        "response_format": "mp3",
    },
)
res.raise_for_status()
with open("hasil.mp3", "wb") as f:
    f.write(res.content)
```

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="YOUR_API_KEY",  # isi "dummy" jika API_KEY kosong di .env
)

with client.audio.speech.with_streaming_response.create(
    model="kokoro",
    voice="af_heart",
    input="Hello! This is running on my local TTS server.",
) as response:
    response.stream_to_file("output.mp3")
```

**Contoh JavaScript / Node.js (`fetch`):**
```javascript
import fs from "node:fs";

const res = await fetch("http://localhost:8000/v1/audio/speech", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer YOUR_API_KEY",
  },
  body: JSON.stringify({
    model: "edge",
    input: "Halo dari LocalTTS!",
    voice: "id-ID-GadisNeural",
    language: "id",
    response_format: "mp3",
  }),
});
const buf = Buffer.from(await res.arrayBuffer());
fs.writeFileSync("hasil.mp3", buf);
```

**Contoh PHP (cURL):**
```php
<?php
$ch = curl_init("http://localhost:8000/v1/audio/speech");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => [
        "Content-Type: application/json",
        "Authorization: Bearer YOUR_API_KEY",
    ],
    CURLOPT_POSTFIELDS => json_encode([
        "model" => "edge",
        "input" => "Halo dari LocalTTS!",
        "voice" => "id-ID-GadisNeural",
        "language" => "id",
        "response_format" => "mp3",
    ]),
]);
$audio = curl_exec($ch);
curl_close($ch);
file_put_contents("hasil.mp3", $audio);
```

**Contoh Go (`net/http`):**
```go
package main

import (
	"bytes"
	"io"
	"net/http"
	"os"
)

func main() {
	body := []byte(`{"model":"edge","input":"Halo dari LocalTTS!","voice":"id-ID-GadisNeural","language":"id"}`)
	req, _ := http.NewRequest("POST", "http://localhost:8000/v1/audio/speech", bytes.NewBuffer(body))
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer YOUR_API_KEY")

	resp, _ := http.DefaultClient.Do(req)
	defer resp.Body.Close()

	out, _ := os.Create("hasil.mp3")
	defer out.Close()
	io.Copy(out, resp.Body)
}
```

---

### `POST /v1/audio/transcriptions` (Whisper Speech-to-Text)
Mengubah file audio/video menjadi teks menggunakan `faster-whisper`.

**Form Fields (`multipart/form-data`):**
| Field | Type | Default | Keterangan |
| :--- | :--- | :--- | :--- |
| `file` | file | *(opsional)* | File audio/video (`mp3`, `wav`, `m4a`, `ogg`, `mp4`, dll) — wajib jika `file_url` kosong |
| `file_url` | string | *(opsional)* | URL publik (`http://` / `https://`) ke file audio/video (maks. 100 MB) — wajib jika `file` kosong |
| `model` | string | `"base"` | `tiny`, `base`, `small`, `medium`, `large-v3-turbo` |
| `language` | string | `null` | Kode bahasa (`id`, `en`) atau kosongkan untuk *auto-detect* |
| `response_format` | string | `"json"` | `json`, `text`, `srt`, `verbose_json` |

**Contoh `curl` (Upload File atau dari URL):**
```bash
# Upload file langsung
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F file=@rekaman.mp3 \
  -F model=base \
  -F language=id \
  -F response_format=verbose_json

# Atau ambil file dari URL
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F file_url="https://example.com/rekaman.mp3" \
  -F model=base \
  -F language=id
```

**Contoh Python (`requests`):**
```python
import requests

with open("rekaman.mp3", "rb") as f:
    res = requests.post(
        "http://localhost:8000/v1/audio/transcriptions",
        headers={"Authorization": "Bearer YOUR_API_KEY"},
        files={"file": f},
        data={"model": "base", "language": "id"},
    )
print(res.json())
```

**Contoh JavaScript / Node.js (`fetch`):**
```javascript
import fs from "node:fs";

const form = new FormData();
form.append("file", new Blob([fs.readFileSync("rekaman.mp3")]), "rekaman.mp3");
form.append("model", "base");
form.append("language", "id");

const res = await fetch("http://localhost:8000/v1/audio/transcriptions", {
  method: "POST",
  headers: { "Authorization": "Bearer YOUR_API_KEY" },
  body: form,
});
console.log(await res.json());
```

**Contoh PHP (cURL):**
```php
<?php
$ch = curl_init("http://localhost:8000/v1/audio/transcriptions");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_HTTPHEADER => ["Authorization: Bearer YOUR_API_KEY"],
    CURLOPT_POSTFIELDS => [
        "file" => new CURLFile("rekaman.mp3"),
        "model" => "base",
        "language" => "id",
    ],
]);
echo curl_exec($ch);
curl_close($ch);
```

---

## 3. Async Job Queue, Progress & Webhook (`/v1/jobs/*`)

Untuk proses berat/lama (seperti *OmniVoice*, *Qwen3-TTS*, atau file audio berdurasi panjang di *Whisper*), gunakan endpoint **Async Job Queue**:
1. Panggil `POST /v1/jobs/speech` atau `POST /v1/jobs/transcriptions` → langsung mendapat `202 Accepted` berisi `job_id`, `queue_position`, dan `status_url`.
2. Pantau progress (`0–100%`) & posisi antrian lewat `GET /v1/jobs/{job_id}`, atau sertakan `webhook_url` (atau set default `WEBHOOK_URL` di `.env`) agar server otomatis mengirim `POST` JSON ke URL Anda saat selesai.
3. Ambil hasil audio / transkrip lewat `GET /v1/jobs/{job_id}/result`.

```bash
# 1. Masukkan ke antrian (dengan webhook opsional)
curl -X POST http://localhost:8000/v1/jobs/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "edge",
    "input": "Halo, ini diproses lewat antrian job!",
    "voice": "id-ID-GadisNeural",
    "language": "id",
    "webhook_url": "https://webhook.site/your-id"
  }'

# 2. Cek progress & nomor antrian
curl http://localhost:8000/v1/jobs/JOB_ID \
  -H "Authorization: Bearer YOUR_API_KEY"

# 3. Download hasil audio setelah status == "completed"
curl http://localhost:8000/v1/jobs/JOB_ID/result \
  -H "Authorization: Bearer YOUR_API_KEY" \
  --output hasil.mp3
```

---

## 4. Studio, Health & Management Endpoints

| Method | Endpoint | Keterangan |
| :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck untuk Docker/Coolify (`{"status": "ok"}`) |
| `GET` | `/api/system` | Info hardware (`CUDA`/`MPS`/`CPU`), RAM, statistik SQLite, & status engine |
| `GET` | `/api/engines` | Daftar engine, kapabilitas, & daftar suara (beserta gender & bahasa) |
| `GET` | `/api/voices/sample` | Preview sample audio pendek (`?engine=edge&voice=id-ID-GadisNeural&language=id`) |
| `POST` | `/api/engines/{name}/load` | Muat model ke memori secara manual |
| `POST` | `/api/engines/{name}/unload` | Lepas model dari memori untuk menghemat RAM/VRAM |
| `POST` | `/api/tts/generate` | Generate TTS via form (mendukung upload `ref_audio` atau `clone_id`) |
| `POST` | `/api/stt/transcribe` | Transkripsi audio via dashboard |
| `GET` | `/api/history` | Daftar riwayat generasi dari SQLite |
| `GET` | `/api/history/{id}/audio` | Unduh/putar file audio dari riwayat |
| `DELETE` | `/api/history/{id}` | Hapus item riwayat |
| `GET` / `POST` / `DELETE` | `/api/clones` | Kelola sample suara untuk *voice cloning* |
