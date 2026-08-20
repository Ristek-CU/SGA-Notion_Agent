# Notion Agent — Python Port & Admin Dashboard

Porting `notion-agent` dari TypeScript/Fastify ke **Python (FastAPI)** + **React Admin Dashboard** (Tailwind CSS v4). Integrasi WhatsApp Bot via Evolution API, Notion Ticketing System, AI Intent & Routing, serta Admin Control Panel.

---

## 🏗️ Tech Stack

- **Backend**: Python 3.11, FastAPI, Uvicorn, `httpx`, `redis-py`, official `anthropic` SDK, `pydantic-settings`, PyJWT, Pytest.
- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS v4, TanStack Query.
- **Infrastructure**: Docker & Docker Compose (Service terpisah Backend & Frontend).

---

## 🚀 Cara Running

### Option 1: Docker Compose (Disarankan)

1. **Salin `.env.example` ke `.env`**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` sesuai kredensial Notion, Anthropic, Redis, dan Evolution API kamu.

2. **Jalankan semua service**:
   ```bash
   docker-compose up -d --build
   ```

3. **Akses Service**:
   - **Frontend Dashboard**: `http://localhost:5173` (atau port public via proxy)
   - **Backend API**: `http://localhost:3000`
   - **Healthcheck**: `http://localhost:3000/health`

---

### Option 2: Running Lokal (Manual)

#### 1. Setup Backend (Python)

```bash
# Buat virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Jalankan Redis (wajib)
docker run -d -p 6379:6379 redis:alpine

# Running server
uvicorn app.main:app --reload --port 3000
```

#### 2. Setup Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

Dashboard dev server akan berjalan di `http://localhost:5173`.

---

## 🧪 Running Unit Tests

```bash
# Jalankan test suite Python
.venv/bin/pytest
```

---

## 🔑 Admin Auth

Secara default kredensial admin login di dashboard diatur via `.env`:
- `ADMIN_USER=admin`
- `ADMIN_PASSWORD=change-this-password`
