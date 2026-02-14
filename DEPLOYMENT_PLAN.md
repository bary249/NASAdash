# OwnerDashV2 — Deployment Plan
**Railway (backend) + Netlify (frontend)**

---

## Architecture Overview

```
LOCAL MACHINE                             CLOUD
┌───────────────────────┐    push_db     ┌────────────────────┐
│ 1. RealPage SSO login │──────────────→ │ Railway             │
│ 2. refresh_all.py     │   (upload      │ FastAPI + uvicorn   │
│    → realpage_raw.db  │    SQLite +    │ Volume: /data       │
│    → unified.db       │    caches)     │  ├ unified.db       │
│    → cache JSONs      │               │  ├ realpage_raw.db  │
│ 3. push_to_deployed.py│               │  └ *_cache.json     │
└───────────────────────┘               └─────────┬──────────┘
                                                  │ /api/*
                                         ┌────────┴──────────┐
                                         │ Netlify            │
                                         │ React SPA (dist/)  │
                                         │ _redirects → Railway│
                                         └───────────────────┘
```

### Why this architecture?

The **RealPage token** is the hard constraint. It requires manual browser SSO
login and expires every ~1 hour. There is no API to refresh it automatically.
This means the full data pipeline (report downloads, SOAP API pulls) **must run
locally** where the token lives. The deployed backend is a **read-only API
server** that serves pre-built SQLite data.

---

## 1. Railway Backend Setup

### 1a. Config files

**`railway.toml`** (new file in `backend/`):
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
restartPolicyType = "on_failure"
healthcheckPath = "/api/auth/me"
healthcheckTimeout = 300
```

**`Procfile`** (new file in `backend/`):
```
web: uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### 1b. Railway Volume

Railway's filesystem is **ephemeral** — wiped on every deploy. SQLite files
must live on a persistent **Railway Volume**.

```bash
# Create project + volume via Railway CLI
railway init
railway volume add --mount /data
```

Mount point: `/data`
Contents after first push:
```
/data/
  unified.db          (~3.7 MB)
  realpage_raw.db     (~23 MB)
  google_reviews_cache.json
  apartments_reviews_cache.json
  google_places_cache.json
  watchpoints.json
```

### 1c. DB Path Abstraction

All code that references `app/db/data/` must resolve to the Railway volume in
production. **Single change point** — update `app/db/__init__.py`:

```python
import os
from pathlib import Path

def get_data_dir() -> Path:
    """Return DB data directory — Railway volume in prod, local in dev."""
    railway_vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "")
    if railway_vol:
        return Path(railway_vol)
    return Path(__file__).parent / "data"

DATA_DIR = get_data_dir()
```

Then replace all `Path(__file__).parent / "data"` references in:
- `app/db/schema.py`
- `app/api/portfolio.py` (multiple sqlite3.connect calls)
- `app/api/routes.py`
- `app/services/google_reviews_service.py`
- `app/services/apartments_reviews_service.py`
- `app/services/watchpoint_service.py`

### 1d. Environment Variables (Railway Dashboard)

```
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=venn-owner-dash-v2-...
ZEMBRA_API_KEY=...
ADMIN_API_KEY=<generate-random-key>    # for DB upload endpoint
RAILWAY_VOLUME_MOUNT_PATH=/data        # auto-set by Railway if volume mounted
```

### 1e. Admin Upload Endpoint

New file: `app/api/admin.py` — protected endpoint to receive DB files from local machine.

```python
@router.post("/admin/upload-db")
async def upload_db(
    file: UploadFile,
    filename: str = Query(...),           # e.g. "unified.db"
    api_key: str = Header(alias="X-Admin-Key"),
):
    if api_key != os.environ.get("ADMIN_API_KEY"):
        raise HTTPException(403, "Invalid admin key")
    
    target = DATA_DIR / filename
    with open(target, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"status": "ok", "filename": filename, "size": len(content)}
```

### 1f. Requirements Update

Add missing deps to `requirements.txt`:
```
bcrypt>=4.0.0
PyJWT>=2.8.0
python-multipart>=0.0.6   # already present, needed for file upload
```

---

## 2. Netlify Frontend Setup

### 2a. Build config

**`netlify.toml`** (new file in `frontend/`):
```toml
[build]
  command = "npm run build"
  publish = "dist"

[build.environment]
  VITE_API_URL = "https://ownerdash-backend.up.railway.app"

[[redirects]]
  from = "/api/*"
  to = "https://ownerdash-backend.up.railway.app/api/:splat"
  status = 200
  force = true

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### 2b. Frontend API Base URL

Update `api.ts` and `AuthContext.tsx` to use env var:

```typescript
// api.ts
const BACKEND_URL = import.meta.env.VITE_API_URL || '';
const API_BASE = `${BACKEND_URL}/api/v2`;
const PORTFOLIO_BASE = `${BACKEND_URL}/api/portfolio`;
```

In development, `VITE_API_URL` is empty → uses Vite proxy.
In production, it's the Railway URL → direct calls.

Actually with the Netlify `_redirects`/`netlify.toml` proxy, we can keep
`VITE_API_URL` empty in prod too and let Netlify proxy `/api/*` → Railway.
This avoids CORS issues entirely. **Recommended approach.**

### 2c. Deploy Commands

```bash
# First time
cd frontend
netlify init   # or netlify link

# Deploy
netlify deploy --prod
```

---

## 3. Data Refresh & Push Workflow

### 3a. Local Pipeline (already exists)

```bash
# 1. Refresh RealPage token (manual browser login)
#    → saves to realpage_token.json

# 2. Run full pipeline
python refresh_all.py

# 3. Push to deployed
python push_to_deployed.py
```

### 3b. `push_to_deployed.py` (new file)

Similar to MessageModeration's pattern but uploads SQLite + cache files:

```python
#!/usr/bin/env python3
"""Push local DB files to deployed Railway backend."""

RAILWAY_URL = "https://ownerdash-backend.up.railway.app"
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "<your-key>")

FILES_TO_PUSH = [
    "app/db/data/unified.db",
    "app/db/data/realpage_raw.db",
    "app/db/data/google_reviews_cache.json",
    "app/db/data/apartments_reviews_cache.json",
    "app/db/data/google_places_cache.json",
    "app/db/data/watchpoints.json",
]

def push_file(filepath, filename):
    with open(filepath, "rb") as f:
        resp = requests.post(
            f"{RAILWAY_URL}/api/admin/upload-db?filename={filename}",
            files={"file": (filename, f)},
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=120,
        )
    return resp

def main():
    for fpath in FILES_TO_PUSH:
        fname = Path(fpath).name
        size_mb = Path(fpath).stat().st_size / 1024 / 1024
        print(f"Pushing {fname} ({size_mb:.1f} MB)...", end=" ")
        resp = push_file(fpath, fname)
        print("✓" if resp.status_code == 200 else f"✗ {resp.text}")
```

### 3c. One-Command Refresh + Deploy

```bash
# Full pipeline: refresh data + push to production
python refresh_all.py && python push_to_deployed.py
```

---

## 4. Automation Options

### Option A: GitHub Actions (code deploys only)

Trigger on push to `main` — deploys code changes, NOT data.

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]

jobs:
  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/cli-action@v1
        with:
          command: up
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: cd frontend && npm ci && npm run build
      - uses: nwtgck/actions-netlify@v3
        with:
          publish-dir: frontend/dist
          production-deploy: true
        env:
          NETLIFY_AUTH_TOKEN: ${{ secrets.NETLIFY_AUTH_TOKEN }}
          NETLIFY_SITE_ID: ${{ secrets.NETLIFY_SITE_ID }}
```

### Option B: Scheduled Data Push (semi-automated)

A local cron job that runs the pipeline at fixed times.
**Caveat**: RealPage token must be fresh (you'd need to refresh it before the cron fires).

```cron
# Every weekday at 7am (you manually refresh token at 6:55am)
0 7 * * 1-5 cd /Users/barak.b/Venn/OwnerDashV2/backend && python refresh_all.py --skip reviews && python push_to_deployed.py
```

### Option C: Railway Cron for Non-Token Tasks

Some refresh tasks don't need RealPage token and could run on Railway directly:
- Apartments.com reviews (Zembra API) ✅
- Risk score recalc (if CSV uploaded) ✅
- Google Reviews (needs Playwright — ❌ won't work on Railway)

Add a `/admin/refresh-reviews` endpoint on Railway that calls Zembra API
directly. Schedule via Railway cron.

### Option D: Token Relay (stretch goal)

Add a `/admin/set-token` endpoint. User pastes the RealPage token via a
simple admin page in the frontend. Railway stores it and can then run limited
report downloads. This avoids pushing DB files — Railway fetches data directly.

**Problem**: Token expires in ~1 hour, so this only works for on-demand
refreshes, not scheduled.

---

## 5. Step-by-Step Implementation Checklist

### Phase 1: Railway Backend (Day 1)
- [ ] Create `railway.toml` and `Procfile` in `backend/`
- [ ] Add `get_data_dir()` abstraction in `app/db/__init__.py`
- [ ] Update all `Path(...) / "data"` references to use `DATA_DIR`
- [ ] Add `bcrypt` and `PyJWT` to `requirements.txt`
- [ ] Create `app/api/admin.py` with upload endpoint
- [ ] Register admin router in `app/main.py`
- [ ] `railway init` → set env vars → attach volume → `railway up`
- [ ] Test: `curl https://<app>.up.railway.app/` → should return API info

### Phase 2: Push Script (Day 1)
- [ ] Create `push_to_deployed.py`
- [ ] Run `refresh_all.py` locally → `push_to_deployed.py`
- [ ] Verify data appears at Railway API endpoints

### Phase 3: Netlify Frontend (Day 1)
- [ ] Create `netlify.toml` with proxy redirects
- [ ] Update `vite.config.ts` for production build
- [ ] `netlify init` → `netlify deploy --prod`
- [ ] Test: login page loads, PHH login works, properties filter correctly

### Phase 4: Automation (Day 2, optional)
- [ ] GitHub Actions for code deploys
- [ ] Local cron for data refresh
- [ ] Railway cron for Zembra reviews

---

## 6. Cost Estimate

| Service  | Tier        | Cost      | Notes                          |
|----------|-------------|-----------|--------------------------------|
| Railway  | Hobby       | ~$5/month | 8GB RAM, 8GB Volume included   |
| Netlify  | Free        | $0        | 100GB bandwidth, auto SSL      |
| **Total**|             | **~$5/mo**|                                |

---

## 7. Risk & Mitigations

| Risk                              | Mitigation                                    |
|-----------------------------------|-----------------------------------------------|
| RealPage token expires mid-pipeline | `refresh_all.py` already handles gracefully  |
| Railway volume data loss          | Keep local DB as source of truth; re-push     |
| SQLite concurrent writes          | Read-only on Railway; writes only via upload   |
| Large DB upload timeout           | Push files individually; use streaming upload  |
| Netlify build fails               | `netlify.toml` pins build command              |
