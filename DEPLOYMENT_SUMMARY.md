# Deployment Architecture Summary

## Overview

**Simplified Architecture: No Local Server**

The Pi runs standalone with SQLite (no local server). It syncs asynchronously to Vercel when internet is available.

Three repositories work together:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REPOSITORY ROLES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. SERVER REPO (save4223/server)                                            │
│     ├─ Deployed to: Vercel (serverless)                                      │
│     ├─ Purpose: Cloud API + Web UI                                           │
│     └─ URL: https://save4223.vercel.app                                      │
│                                                                              │
│  2. CABINET-PI REPO (save4223/cabinet-pi)                                    │
│     ├─ Runs on: Raspberry Pi (local)                                         │
│     ├─ Purpose: Edge controller + Local cache                                │
│     └─ Local DB: SQLite (/home/pi/data/local.db)                             │
│                                                                              │
│  3. MAIN REPO (save4223) - PARENT                                            │
│     ├─ Contains: Documentation + Architecture                                │
│     └─ Submodules: server/, cabinet-pi/                                      │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Repository Details

### 1. SERVER Repo (save4223/server)

**Location:** `~/save4223/server`
**Deploy to:** Vercel
**Branch:** `main` (admin dashboard changes stashed)

**What it does:**
- Serves web UI (Next.js app) for users to browse items, view history
- Provides API endpoints for Pi to sync data
- Stores data in Supabase Cloud (PostgreSQL)

**Key Files:**
```
server/
├── src/app/api/edge/         # Pi API endpoints
│   ├── authorize/            # POST /api/edge/authorize
│   ├── sync-session/         # POST /api/edge/sync-session
│   ├── local-sync/           # GET /api/edge/local-sync
│   └── pair-card/            # POST /api/edge/pair-card
├── src/app/user/             # User web UI
├── src/app/admin/            # Admin web UI
└── vercel.json               # Vercel deployment config
```

**How to deploy:**
```bash
cd ~/save4223/server

# Install dependencies
npm install

# Build
npm run build

# Deploy to Vercel
vercel --prod
```

**Environment Variables (in Vercel Dashboard):**
```
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
EDGE_API_SECRET=generate-a-random-secret
```

---

### 2. CABINET-PI Repo (save4223/cabinet-pi)

**Location:** `~/save4223/cabinet-pi`
**Runs on:** Raspberry Pi (physical device) - **NO LOCAL SERVER**
**Language:** Python 3.12+

**What it does:**
- Controls hardware (NFC reader, RFID scanner, servos, LEDs)
- Runs state machine (LOCKED → AUTHENTICATING → UNLOCKED → SCANNING)
- **Local SQLite** for offline auth and session storage
- **Async/sync to Vercel** when internet available (background thread)
- Shows display UI (NiceGUI) on local screen

**NO local server runs on Pi** - just the Python controller with SQLite cache.

**Key Files:**
```
cabinet-pi/
├── src/
│   ├── main.py               # Main entry point
│   ├── state_machine.py      # Cabinet state logic
│   ├── api_client.py         # Cloud API client
│   ├── local_db.py           # SQLite database
│   ├── sync_worker.py        # Background cloud sync
│   └── hardware/
│       ├── mock.py           # Mock hardware for testing
│       └── raspberry_pi.py   # Real hardware (to implement)
├── display/
│   └── display.py            # NiceGUI display UI
├── config.json               # Pi configuration
└── pyproject.toml            # uv dependencies
```

**How to run:**
```bash
cd ~/save4223/save4223-cabinet-pi

# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Configure
cp config.cloud.example.json config.json
# Edit config.json with your Vercel URL

# Run
uv run python -m src.main
```

**Configuration (config.json):**
```json
{
    "server_url": "https://save4223.vercel.app",
    "edge_secret": "same-secret-as-vercel",
    "cabinet_id": 1,
    "db_path": "./data/local.db",
    "hardware": {
        "mode": "mock"
    }
}
```

---

### 3. Do You Need a Local Server?

**NO** - There is no local server. The architecture is intentionally simple:

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ Raspberry Pi │ ──────► │    Vercel    │ ──────► │  Supabase    │
│  (SQLite)    │  HTTP   │  (Next.js)   │  SQL    │  (Cloud DB)  │
└──────────────┘         └──────────────┘         └──────────────┘
       │
       │ No internet? No problem!
       │ SQLite handles auth locally
       └────────────────────────────►
```

**Pi runs standalone:**
- Local SQLite for user auth (cached from cloud)
- Local SQLite for session/transaction storage
- Background thread syncs to Vercel when online
- NiceGUI display runs directly (no server needed)

---

## Data Flow Summary

### 1. Card Tap → Unlock (Local SQLite, No Internet Needed)
```
┌─────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ NFC Card│───►│ Raspberry Pi │───►│ Local SQLite │───►│ Unlock Drawer│
│  Tap    │    │  (Python)    │    │(cached users)│    │              │
└─────────┘    └──────────────┘    └──────────────┘    └──────────────┘
      │                                                  │
      │ No internet?                                     │
      │ Works fine!                                      │
      ▼                                                  ▼
   ┌──────────────┐                              ┌──────────────┐
   │ Log session  │                              │ User takes   │
   │ locally in   │                              │ tools        │
   │ SQLite       │                              │              │
   └──────────────┘                              └──────────────┘
```

### 2. Async Sync to Cloud (Background, When Online)
```
┌──────────────┐
│  Sync Worker │ ◄────────── Background thread wakes up periodically
│   Thread     │              or when network becomes available
└──────┬───────┘
       │
       ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Unsynced     │───►│ POST /api/   │───►│  Supabase    │
│ sessions in  │    │ edge/sync-   │    │  Cloud DB    │
│ SQLite       │    │ session      │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
       │                                     │
       │ Mark as synced                      │
       ▼                                     ▼
┌──────────────┐                    ┌──────────────┐
│ Update local │                    │ Web UI shows │
│ sync status  │                    │ new data     │
└──────────────┘                    └──────────────┘
```

### 3. User Views Web UI (Cloud)
```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ User Opens   │───►│ Vercel       │───►│ Supabase     │
│ Browser      │    │ (Next.js)    │    │ (Cloud DB)   │
└──────────────┘    └──────────────┘    └──────────────┘
                           │
                           │ Real-time subscription
                           ▼
                    ┌──────────────┐
                    │ Sees synced  │
                    │ session data │
                    └──────────────┘
```

---

## Quick Start Checklist

### 1. Set Up Supabase Cloud (10 mins)
- [ ] Create project at supabase.com
- [ ] Run database migrations
- [ ] Copy API keys

### 2. Deploy Server to Vercel (10 mins)
```bash
cd ~/save4223/server
git stash  # (already done)
git checkout main
npm install
vercel --prod
```
- [ ] Set environment variables in Vercel dashboard

### 3. Configure Pi (10 mins)
```bash
cd ~/save4223/save4223-cabinet-pi
cp config.cloud.example.json config.json
# Edit config.json with Vercel URL
uv sync
uv run python -m src.main
```
- [ ] Test card tap
- [ ] Test checkout
- [ ] Verify data appears in web UI

---

## File Changes Summary

### On Stash (feat/admin-usage-dashboard branch):
- Admin dashboard features
- Analytics service
- Alert service
- Email service

### To Implement (main branch):
- Vercel deployment config ✅
- Edge API routes ✅ (already exist)
- Pi cloud configuration ✅

### Next Steps:
1. Unstash admin features after cloud deployment works
2. Merge admin features to main
3. Re-deploy to Vercel

---

## Questions?

**Q: Do I need to run `npm run dev` on my local machine?**
A: No. Only deploy to Vercel. Local dev is for testing only.

**Q: What runs on the Pi?**
A: Only the cabinet-pi Python app (`uv run python -m src.main`)

**Q: Where is the database?**
A: Supabase Cloud (not local PostgreSQL)

**Q: Can I still use local Supabase for testing?**
A: Yes, just change the URL in Vercel env vars to local.

**Q: What runs on the Pi?**
A: A Python script (`uv run python -m src.main`) that:
   - Controls hardware directly
   - Uses SQLite for local storage
   - Has a background thread for cloud sync
   - Shows NiceGUI display
   - **NO separate server process needed**

**Q: What if internet goes down?**
A: Pi works 100% offline using local SQLite cache. It queues sessions and syncs when back online.
