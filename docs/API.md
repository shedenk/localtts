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

**Contoh Python (OpenAI SDK):**
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

---

### `POST /v1/audio/transcriptions` (Whisper Speech-to-Text)
Mengubah file audio/video menjadi teks menggunakan `faster-whisper`.

**Form Fields (`multipart/form-data`):**
| Field | Type | Default | Keterangan |
| :--- | :--- | :--- | :--- |
| `file` | file | *(wajib)* | File audio/video (`mp3`, `wav`, `m4a`, `ogg`, `mp4`, dll) |
| `model` | string | `"base"` | `tiny`, `base`, `small`, `medium`, `large-v3-turbo` |
| `language` | string | `null` | Kode bahasa (`id`, `en`) atau kosongkan untuk *auto-detect* |
| `response_format` | string | `"json"` | `json`, `text`, `srt`, `verbose_json` |

**Contoh `curl`:**
```bash
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F file=@rekaman.mp3 \
  -F model=base \
  -F language=id \
  -F response_format=verbose_json
```

---

## 3. Studio, Health & Management Endpoints

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
