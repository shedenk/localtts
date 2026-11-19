# LocalTTS

Self-hosted **Text-to-Speech (TTS)** & **Speech-to-Text (STT)** hub dengan antarmuka web sederhana, **OpenAI-compatible API**, riwayat **SQLite**, deteksi hardware otomatis (`CUDA` / `Apple MPS` / `CPU`), dan autentikasi berbasis `.env`.

Fokus pada **Bahasa Inggris (`en`)** dan **Bahasa Indonesia (`id`)**, lengkap dengan filter gender (`Female` / `Male`) serta **tombol preview sample pendek** di setiap suara.

---

## Fitur Utama

- **Multi-Engine TTS & STT dalam 1 Service:**
  - **[Kokoro-82M (`kokoro-onnx`)](https://github.com/thewh1teagle/kokoro-onnx):** Ringan, cepat di CPU/macOS/VPS, kualitas natural untuk Bahasa Inggris.
  - **[Edge-TTS (`rany2/edge-tts`)](https://github.com/rany2/edge-tts):** Suara neural gratis untuk Bahasa Indonesia & Inggris dengan beban CPU/RAM hampir nol.
  - **[OmniVoice (`k2-fsa/OmniVoice`)](https://github.com/k2-fsa/OmniVoice):** Mendukung Bahasa Indonesia & Inggris, *zero-shot voice cloning*, dan *voice design*.
  - **[Qwen3-TTS (`QwenLM/Qwen3-TTS`)](https://github.com/QwenLM/Qwen3-TTS):** TTS ekspresif dengan *voice cloning* 3 detik & kontrol instruksi.
  - **[Faster-Whisper](https://github.com/SYSTRAN/faster-whisper):** Transkripsi audio/video (STT) via upload file (`MP3`, `AAC`, `WAV`, `M4A`, dll) atau **URL (`file_url`)** dengan download hasil **TXT / CSV / SRT**.
- **UI Sederhana & Informatif (5 Tab):**
  - **🔊 TTS Studio:** Layout 2-kolom dengan kartu pilihan suara (badge **Gender** & **Bahasa**, tombol **▶ Sample** bawaan di `web/samples/`), *Voice Cloning*, serta **TTS History** langsung di bawahnya (highlight `✨ NEW` untuk hasil terbaru, **👁 Lihat** teks, **⬇ Download**, checkbox select/hapus/pagination).
  - **📝 Whisper STT:** Upload file atau masukkan URL audio/video, download hasil **TXT / CSV / SRT**, serta **Whisper STT History** di bawahnya (**👁 Lihat**, **Copy**, **⬇ TXT/CSV**, select/hapus/pagination).
  - **🎭 Voice Clones:** Kelola sample audio referensi untuk *voice cloning*.
  - **⚡ API Docs:** Dokumentasi interaktif dengan contoh **cURL, Python, JavaScript, PHP, dan Go** (otomatis terisi `API_KEY` aktif).
  - **🖥️ System & Credits:** Monitor RAM/CPU/GPU (`CUDA` / `MPS` / `CPU`), Load/Unload model, tombol **⬇ Install from UI** untuk OmniVoice & Qwen3-TTS sesuai spek perangkat, dan daftar sumber open-source.
- **Manajemen Memori Otomatis:** *Lazy-load* saat dipakai dan *auto-unload* setelah idle (`IDLE_UNLOAD_SECONDS`).
- **SQLite Database:** Menyimpan riwayat generasi TTS/STT, sample *voice clone*, dan log API di `data/tts_local.db`.
- **Keamanan `.env` Only (Tanpa Setup DB User):**
  - Login UI menggunakan `AUTH_USERNAME` & `AUTH_PASSWORD` (kosongkan jika ingin tanpa login).
  - API menggunakan `API_KEY` via header `Authorization: Bearer` atau `X-API-Key` (kosongkan jika API ingin terbuka tanpa header).
- **OpenAI-Compatible API & Async Job Queue:** Siap dihubungkan ke **OpenWebUI**, **n8n**, **LangChain**, atau **OpenAI SDK**, serta menyediakan `/v1/jobs/*` dengan nomor antrian, progress `0–100%`, dan notifikasi **Webhook** (`WEBHOOK_URL` di `.env` atau per-request).

---

## Spesifikasi Minimum

| Mode | CPU | RAM | Storage | GPU |
| :--- | :--- | :--- | :--- | :--- |
| **Mode Standar (Default)**<br>*(Edge-TTS, Kokoro-82M, Whisper `tiny`/`base`)* | 1–2 vCPU | **1–2 GB** | 2–3 GB | Tidak perlu (CPU only) |
| **Mode Lengkap (`--all` / Install dari UI)**<br>*(+ OmniVoice & Qwen3-TTS)* | 4+ vCPU / Apple Silicon | **8–16 GB** | 15–25 GB | Opsional (NVIDIA VRAM ≥ 6–8 GB atau Apple MPS) |

> **Catatan:** Model dimuat secara *lazy-load* dan otomatis di-unload saat idle (`IDLE_UNLOAD_SECONDS=300`) agar hemat RAM/VRAM.

---

## Instalasi & Menjalankan

### 1. macOS (Apple Silicon / Intel)

> Disarankan menjalankan langsung secara native (bukan Docker) agar PyTorch dapat memanfaatkan akselerasi **Apple Silicon MPS**.

```bash
git clone https://github.com/shedenk/localtts.git
cd localtts
chmod +x scripts/setup-mac.sh scripts/run-mac.sh

# Install standar (ringan: Kokoro, Edge-TTS, Faster-Whisper) — OmniVoice & Qwen3-TTS bisa diinstall dari UI nanti
./scripts/setup-mac.sh

# (Opsional) Install semua engine sekaligus dari CLI:
# ./scripts/setup-mac.sh --all

# Jalankan server
./scripts/run-mac.sh
```
Buka `http://localhost:8000` (login default di `.env`: `admin` / `changeme123`).

---

### 2. Linux (Ubuntu / Debian / Fedora)

```bash
git clone https://github.com/shedenk/localtts.git
cd localtts
chmod +x scripts/setup-linux.sh

# Install standar (atau tambah --all untuk langsung install OmniVoice & Qwen3-TTS)
./scripts/setup-linux.sh

# Jalankan server
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### 3. Windows (PowerShell)

> Pastikan `ffmpeg` sudah terpasang (`winget install Gyan.FFmpeg`).

```powershell
git clone https://github.com/shedenk/localtts.git
cd localtts

# Install standar (atau tambah --all untuk langsung install OmniVoice & Qwen3-TTS)
.\scripts\setup-win.ps1

# Jalankan server
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

---

### 4. Docker & Docker Compose

```bash
git clone https://github.com/shedenk/localtts.git
cd localtts
cp .env.example .env

# Jalankan (build standar ringan: Kokoro, Edge-TTS, Faster-Whisper + volume persistent)
docker compose up -d --build
```
Untuk langsung menginstal OmniVoice & Qwen3-TTS saat build Docker, set `INSTALL_ALL_ENGINES=true` di `.env` atau environment panel (butuh RAM ≥ 8 GB / GPU). Anda juga bisa menginstallnya belakangan langsung dari tab **🖥️ System & Credits** di UI.

---

### 5. Deploy di Panel Populer (Coolify, Dokploy, Portainer, EasyPanel)

#### **Coolify**
1. Pilih **New Resource → Public/Private Repository** → masukkan URL repo GitHub ini.
2. Pilih **Build Pack: Docker Compose**, lalu isi **Docker Compose Location** dengan `docker-compose.coolify.yaml` (file khusus Coolify dengan `expose`, `healthcheck`, dan `SERVICE_FQDN_LOCALTTS`).
3. Di menu **Environment Variables**, atur:
   - `AUTH_USERNAME=admin`
   - `AUTH_PASSWORD=password_kuat_anda`
   - `SESSION_SECRET=random_string_panjang`
   - `API_KEY=` *(kosongkan jika API tanpa header, atau isi dengan secret key Anda)*
   - `INSTALL_ALL_ENGINES=false` *(default `false` untuk build cepat & ringan; set `true` jika VPS RAM ≥ 8 GB / GPU, atau install dari UI nanti)*
4. Pastikan **Persistent Storage** untuk `/app/data` (SQLite + hasil audio) dan `/app/models` (cache model) aktif (sudah terkonfigurasi di `docker-compose.yml`).
5. Klik **Deploy** dan arahkan domain Anda ke port `8000`.

#### **Dokploy / EasyPanel / Portainer**
- **Dokploy:** Buat **Compose Service** dari repo GitHub, isi environment variables di tab *Environment*, lalu *Deploy*.
- **Portainer:** Masuk ke **Stacks → Add stack → Repository**, pilih `docker-compose.yml`, isi environment variables, lalu **Deploy the stack**.
- **EasyPanel:** Buat **App** dari GitHub dengan **Dockerfile**, tambahkan *Mounts* ke `/app/data` dan `/app/models`, set port `8000`, dan isi environment variables.

---

## Konfigurasi Environment (`.env`)

| Variable | Default | Keterangan |
| :--- | :--- | :--- |
| `PORT` | `8000` | Port server HTTP |
| `AUTH_USERNAME` | `admin` | Username login UI (kosongkan untuk menonaktifkan login UI) |
| `AUTH_PASSWORD` | `changeme123` | Password login UI (kosongkan untuk menonaktifkan login UI) |
| `SESSION_SECRET` | `...` | Secret key untuk cookie session UI |
| `API_KEY` | *(kosong)* | Jika kosong, API `/v1/*` terbuka; jika diisi, wajib kirim Bearer / `X-API-Key` |
| `API_KEY_HEADER` | `X-API-Key` | Nama header kustom alternatif selain `Authorization: Bearer` |
| `DEVICE` | `auto` | `auto` \| `cuda` \| `mps` \| `cpu` |
| `ENABLED_ENGINES` | `kokoro,edge,whisper,omnivoice,qwen3` | Daftar engine yang diaktifkan |
| `IDLE_UNLOAD_SECONDS` | `300` | Otomatis unload model dari RAM setelah idle (detik). `0` = nonaktif |
| `TTS_MAX_CHARS` | `5000` | Batas maksimal karakter teks untuk TTS (`0` = tanpa batas) |
| `STT_MAX_FILE_MB` | `50` | Batas maksimal ukuran file audio/video (MB) untuk transkrip STT (`0` = tanpa batas) |
| `WEBHOOK_URL` | *(kosong)* | Default URL webhook untuk notifikasi *async job* (`/v1/jobs/*`) saat selesai |
| `ALLOW_LOCAL_URLS` | `true` | Izinkan `localhost`/`127.0.0.1` pada `file_url` & `webhook_url` (set `false` di VPS publik ketat) |

---

## Dokumentasi API

LocalTTS menyediakan endpoint **OpenAI-compatible (`/v1/audio/*`)** serta **Async Job Queue (`/v1/jobs/*`)** dengan progress tracking (`0–100%`), nomor antrian, dan **Webhook**.

### Autentikasi API
- Jika `API_KEY` di `.env` **kosong**: semua endpoint `/v1/*` terbuka tanpa header.
- Jika `API_KEY` **diisi** (misal `API_KEY=apikey123`): kirim salah satu header berikut:
  - `Authorization: Bearer apikey123`
  - `X-API-Key: apikey123`

### Daftar Endpoint Utama

| Method | Endpoint | Keterangan |
| :--- | :--- | :--- |
| `GET` | `/v1/models` | Daftar engine yang siap dipakai (`kokoro`, `edge`, `omnivoice`, `qwen3`, `whisper`) |
| `POST` | `/v1/audio/speech` | Text-to-Speech langsung (mengembalikan binary audio `mp3`/`wav`/`opus`/`flac`) |
| `POST` | `/v1/audio/transcriptions` | Whisper STT langsung (upload `file` atau `file_url`, output `json`/`text`/`srt`/`verbose_json`) |
| `POST` | `/v1/jobs/speech` | Async Queue TTS (mengembalikan `202` + `job_id` + `queue_position`, mendukung `webhook_url`) |
| `POST` | `/v1/jobs/transcriptions` | Async Queue STT (`file` / `file_url` + opsional `webhook_url`) |
| `GET` | `/v1/jobs/{job_id}` | Cek status (`queued`/`processing`/`completed`/`failed`), `progress`, `stage`, & `queue_position` |
| `GET` | `/v1/jobs/{job_id}/result` | Ambil file audio TTS atau hasil transkrip STT setelah `status == "completed"` |
| `GET` | `/health` | Healthcheck server (`{"status": "ok"}`, tanpa auth) |

### Contoh Request & Response

#### 1. Text-to-Speech (`POST /v1/audio/speech`)
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer apikey123" \
  -d '{"model":"edge","input":"Halo dari server LocalTTS!","voice":"id-ID-GadisNeural","language":"id","response_format":"mp3"}' \
  --output halo.mp3
```
**Response (`200 OK`):** Binary audio (`Content-Type: audio/mpeg`) beserta header `X-Process-Seconds` dan `X-Audio-Duration`.

#### 2. Whisper STT (`POST /v1/audio/transcriptions`)
```bash
# Upload file langsung (MP3/AAC/WAV/M4A) atau pakai file_url
curl -X POST http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer apikey123" \
  -F "file=@audio.mp3" \
  -F "model=base" \
  -F "language=id" \
  -F "response_format=verbose_json"
```
**Response (`200 OK`):**
```json
{
  "text": "Halo dari server LocalTTS.",
  "language": "id",
  "duration": 2.4,
  "segments": [{"id": 1, "start": 0.0, "end": 2.4, "text": "Halo dari server LocalTTS."}],
  "process_sec": 0.62
}
```

#### 3. Async Job Queue, Progress & Webhook (`POST /v1/jobs/speech`)
```bash
# 1. Enqueue job (webhook_url opsional, default pakai WEBHOOK_URL di .env)
curl -X POST http://localhost:8000/v1/jobs/speech \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer apikey123" \
  -d '{"model":"omnivoice","input":"Teks panjang...","voice":"id_female","language":"id","webhook_url":"https://webhook.site/id"}'
```
**Response (`202 Accepted`):**
```json
{
  "job_id": "job_133614501c17",
  "kind": "tts",
  "status": "queued",
  "progress": 0,
  "queue_position": 1,
  "status_url": "/v1/jobs/job_133614501c17",
  "result_url": "/v1/jobs/job_133614501c17/result"
}
```
Cek progress via `GET /v1/jobs/job_133614501c17`, dan ambil hasil akhir via `GET /v1/jobs/job_133614501c17/result`. Jika `webhook_url` / `WEBHOOK_URL` diisi, server otomatis mengirim `POST` JSON berisi `job_id`, `status`, `progress`, `result`, dan `error` saat selesai.

### Kode Error Umum
- `400 Bad Request`: Parameter tidak valid / model tidak dikenal / URL bukan `http`/`https`.
- `401 Unauthorized`: `API_KEY` aktif di `.env` namun header `Authorization` / `X-API-Key` tidak valid atau kosong.
- `404 Not Found`: `job_id` atau resource tidak ditemukan.
- `413 Payload Too Large`: Teks melebihi `TTS_MAX_CHARS` atau file melebihi `STT_MAX_FILE_MB`.
- `503 Service Unavailable`: Engine belum terinstall di server.

Contoh lengkap untuk **Python, JavaScript/Node.js, PHP, dan Go** tersedia di **[docs/API.md](docs/API.md)** serta langsung di tab **⚡ API Docs** pada UI (bisa export ke `.md`, `.txt`, dan `.csv`).

---

## Lisensi & Disclaimer Legalitas

- **Kode Aplikasi:** Dirilis di bawah [MIT License](LICENSE).
- **Merek Dagang:** LocalTTS adalah proyek independen dan tidak berafiliasi dengan OpenAI, Microsoft, atau Alibaba. Penyebutan *"OpenAI-compatible"* hanya merujuk pada kompatibilitas format API.
- **Engine Pihak Ketiga:** Masing-masing engine mengikuti lisensinya sendiri (Kokoro-82M, Faster-Whisper, OmniVoice, Qwen3-TTS menggunakan lisensi permisif MIT/Apache-2.0). Khusus `edge-tts` menggunakan layanan online Microsoft Edge secara tidak resmi — gunakan hanya untuk pengujian/pribadi; untuk kebutuhan produksi/komersial, gunakan engine lokal offline (`kokoro`, `omnivoice`, atau `qwen3`).
- **Voice Cloning:** Fitur *voice cloning* hanya boleh digunakan dengan suara milik sendiri atau atas izin eksplisit pemilik suara. Jangan gunakan untuk peniruan identitas tanpa izin.
