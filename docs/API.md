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

### Whitelist IP & Domain (`ALLOWED_IPS` & `ALLOWED_DOMAINS`)
Anda juga dapat membatasi akses ke seluruh server (UI maupun API) hanya untuk IP atau domain tertentu:
- **`ALLOWED_IPS`**: Daftar IP/CIDR dipisah koma (contoh: `127.0.0.1,::1,103.10.20.30,192.168.1.0/24`). Mendukung header proxy `CF-Connecting-IP` (Cloudflare), `X-Forwarded-For` (Coolify/Traefik/Nginx), dan `X-Real-IP`.
- **`ALLOWED_DOMAINS`**: Daftar domain atau wildcard subdomain dipisah koma (contoh: `tts.myminio.cloud,app.domain.com,*.domain.com`). Memvalidasi header `Origin` / `Referer` (untuk panggilan lintas domain) atau `Host`.
- Request dari IP/domain di luar daftar akan ditolak dengan status **`403 Forbidden`** dan dicatat pada System Logs. Endpoint `/health` selalu diizinkan agar healthcheck Docker/Coolify tetap berjalan normal.

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
| `GET` | `/api/system` | Info hardware (`CUDA`/`MPS`/`CPU`), RAM, storage (total/used/free), statistik SQLite, & status engine |
| `GET` | `/api/system/logs` | Log runtime sistem (parameter: `?level=ALL|INFO|WARNING|ERROR&limit=200`) |
| `POST` | `/api/system/logs/clear` | Mengosongkan log sistem dari memori dan file |
| `POST` | `/api/system/clean` | Memicu pembersihan storage manual (file audio lama > N hari & rotasi log) |
| `GET` | `/api/settings` | Mengambil seluruh konfigurasi environment (`.env`) aktif |
| `POST` | `/api/settings` | Menyimpan perubahan konfigurasi ke file `.env` dan langsung di-reload ke server |
| `GET` | `/api/engines` | Daftar engine, kapabilitas, & daftar suara (beserta gender & bahasa) |
| `GET` | `/api/voices/sample` | Preview sample audio pendek (`?engine=edge&voice=id-ID-GadisNeural&language=id`) |
| `POST` | `/api/engines/{name}/load` | Muat model ke memori secara manual |
| `POST` | `/api/engines/{name}/unload` | Lepas model dari memori untuk menghemat RAM/VRAM |
| `POST` | `/api/tts/generate` | Generate TTS via form (mendukung upload `ref_audio` atau `clone_id`) |
| `POST` | `/api/stt/transcribe` | Transkripsi audio via dashboard |
| `GET` | `/api/history` | Daftar riwayat generasi dari SQLite (filter jenis, pagination, counter header) |
| `POST` | `/api/history/bulk-delete` | Hapus beberapa riwayat sekaligus (`{"ids": [1, 2, 3]}`) |
| `GET` | `/api/history/{id}/audio` | Unduh/putar file audio dari riwayat |
| `DELETE` | `/api/history/{id}` | Hapus satu item riwayat |
| `GET` / `POST` / `DELETE` | `/api/clones` | Kelola sample suara untuk *voice cloning* |

---

## 5. Storage Auto-Clean & System Logs API

### `GET /api/system/logs`
Mengambil baris log live sistem dari memori dan file `data/localtts.log`.

**Query Parameters:**
- `level`: `ALL` (default), `INFO`, `WARNING`, `ERROR`
- `limit`: Jumlah maksimal baris log (default: 200, maks: 500)

**Contoh Response:**
```json
{
  "logs": [
    {
      "timestamp": "2026-11-19 14:32:01",
      "level": "INFO",
      "category": "SYSTEM",
      "source": "SYSTEM",
      "message": "LocalTTS application started successfully."
    }
  ]
}
```

### `POST /api/system/clean`
Menjalankan pemeriksaan storage dan pembersihan file audio output lama atau rotasi log secara instan tanpa menunggu jadwal cron berkala.

**Contoh Response:**
```json
{
  "ok": true,
  "cleaned_files": 12,
  "cleaned_by_age": 5,
  "cleaned_by_threshold": 7,
  "freed_mb": 4.82,
  "disk_percent_before": 78.4,
  "disk_percent_after": 72.1,
  "disk_free_gb": 18.5,
  "pruned_db_logs": 240,
  "log_file_status": {
    "rotated": false,
    "pruned_lines": 120,
    "size_mb": 1.2
  }
}
```

---

## 6. Settings API (`/api/settings`)

Mengambil atau memperbarui konfigurasi environment `.env` secara visual dari UI maupun sistem otomatisasi.

### `GET /api/settings`
Mengembalikan status konfigurasi aktif server.

### `POST /api/settings`
Memperbarui file `.env` di disk dan langsung memuat ulang nilainya ke runtime aplikasi tanpa restart manual.

**Request Body (JSON):**
```json
{
  "app_name": "LocalTTS Production",
  "port": 8000,
  "auth_username": "admin",
  "auth_password": "supersecretpassword",
  "api_key": "ltk_customsecretkey123456",
  "device": "auto",
  "enabled_engines": "kokoro,edge,whisper,omnivoice,qwen3",
  "idle_unload_seconds": 300,
  "tts_max_chars": 5000,
  "stt_max_file_mb": 50,
  "webhook_url": "https://webhook.site/my-id",
  "allow_local_urls": true,
  "auto_clean_disk_percent": 75,
  "auto_clean_retention_days": 30,
  "log_retention_days": 3,
  "log_max_mb": 10
}
```
