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
  - **[Faster-Whisper](https://github.com/SYSTRAN/faster-whisper):** Transkripsi audio/video (STT) cepat dengan output JSON, Text, dan SRT.
- **UI Sederhana & Informatif:**
  - Kartu pilihan suara dengan badge **Gender** & **Bahasa**, serta tombol **▶ Sample** untuk mendengar contoh suara sebelum generate.
  - Monitor penggunaan RAM, device aktif (`CUDA` / `MPS` / `CPU`), dan status model yang sedang *loaded*.
- **Manajemen Memori Otomatis:** *Lazy-load* saat dipakai dan *auto-unload* setelah idle (`IDLE_UNLOAD_SECONDS`).
- **SQLite Database:** Menyimpan riwayat generasi TTS/STT, sample *voice clone*, dan log API di `data/tts_local.db`.
- **Keamanan `.env` Only (Tanpa Setup DB User):**
  - Login UI menggunakan `AUTH_USERNAME` & `AUTH_PASSWORD` (kosongkan jika ingin tanpa login).
  - API menggunakan `API_KEY` via header `Authorization: Bearer` atau `X-API-Key` (kosongkan jika API ingin terbuka tanpa header).
- **OpenAI-Compatible API:** Siap dihubungkan ke **OpenWebUI**, **n8n**, **LangChain**, atau **OpenAI SDK**.

---

## Spesifikasi Minimum

| Mode | CPU | RAM | Storage | GPU |
| :--- | :--- | :--- | :--- | :--- |
| **Mode Ringan (`--lite`)**<br>*(Edge-TTS, Kokoro-82M, Whisper `tiny`/`base`)* | 1–2 vCPU | **1–2 GB** | 2–3 GB | Tidak perlu (CPU only) |
| **Mode Lengkap (Semua Engine)**<br>*(+ OmniVoice & Qwen3-TTS)* | 4+ vCPU / Apple Silicon | **8–16 GB** | 15–25 GB | Opsional (NVIDIA VRAM ≥ 6–8 GB atau Apple MPS) |

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

# Jalankan (otomatis build dengan semua engine & volume persistent)
docker compose up -d --build
```
Untuk VPS dengan RAM kecil (misal 1–2 GB), set `INSTALL_ALL_ENGINES=false` di `.env` atau environment panel sebelum build agar hanya menginstal **Kokoro + Edge-TTS + Faster-Whisper**.

---

### 5. Deploy di Panel Populer (Coolify, Dokploy, Portainer, EasyPanel)

#### **Coolify**
1. Pilih **New Resource → Public/Private Repository** → masukkan URL repo GitHub ini.
2. Pilih **Build Pack: Docker Compose** (akan otomatis membaca [docker-compose.yml](docker-compose.yml)).
3. Di menu **Environment Variables**, atur:
   - `AUTH_USERNAME=admin`
   - `AUTH_PASSWORD=password_kuat_anda`
   - `SESSION_SECRET=random_string_panjang`
   - `API_KEY=` *(kosongkan jika API tanpa header, atau isi dengan secret key Anda)*
   - `INSTALL_ALL_ENGINES=true` *(ubah ke `false` jika VPS RAM < 4 GB)*
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

---

## Dokumentasi API

Dokumentasi lengkap seluruh endpoint OpenAI-compatible (`/v1/audio/speech`, `/v1/audio/transcriptions`), Voice Cloning, dan contoh integrasi Python/cURL tersedia di **[docs/API.md](docs/API.md)**.

Contoh cepat TTS Bahasa Indonesia:
```bash
curl -X POST http://localhost:8000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"edge","input":"Halo dari server TTS lokal!","voice":"id-ID-GadisNeural","language":"id"}' \
  --output halo.mp3
```

---

## Lisensi & Disclaimer Legalitas

- **Kode Aplikasi:** Dirilis di bawah [MIT License](LICENSE).
- **Merek Dagang:** LocalTTS adalah proyek independen dan tidak berafiliasi dengan OpenAI, Microsoft, atau Alibaba. Penyebutan *"OpenAI-compatible"* hanya merujuk pada kompatibilitas format API.
- **Engine Pihak Ketiga:** Masing-masing engine mengikuti lisensinya sendiri (Kokoro-82M, Faster-Whisper, OmniVoice, Qwen3-TTS menggunakan lisensi permisif MIT/Apache-2.0). Khusus `edge-tts` menggunakan layanan online Microsoft Edge secara tidak resmi — gunakan hanya untuk pengujian/pribadi; untuk kebutuhan produksi/komersial, gunakan engine lokal offline (`kokoro`, `omnivoice`, atau `qwen3`).
- **Voice Cloning:** Fitur *voice cloning* hanya boleh digunakan dengan suara milik sendiri atau atas izin eksplisit pemilik suara. Jangan gunakan untuk peniruan identitas tanpa izin.
