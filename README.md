# Save4223 - Smart Lab Inventory System

[![GitHub](https://img.shields.io/badge/GitHub-save4223-blue)](https://github.com/save4223/save4223)

**ISDN Smart Inventory & Tool Cabinet (V2)**

A cloud-edge hybrid inventory management system for labs and workshops. Features real-time RFID tracking, session-based auditing, offline-capable edge devices, and automated overdue notifications.

## 🏗️ Architecture

```
┌─────────────────────────────────────┐
│         Cloud Server (Linux)        │
│  ┌─────────────────────────────┐    │
│  │      Next.js 15 App         │    │
│  │  - Web Dashboard            │    │
│  │  - REST API                 │    │
│  │  - Admin Panel              │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │    PostgreSQL (Supabase)    │    │
│  │  - User Profiles            │    │
│  │  - Inventory Data           │    │
│  │  - Session Audit Logs       │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │   MinIO (Object Storage)    │    │
│  │  - Tool Images              │    │
│  │  - CCTV Snapshots           │    │
│  └─────────────────────────────┘    │
└──────────────┬──────────────────────┘
               │ HTTP/REST
               │ (Pi as Client)
┌──────────────▼──────────────────────┐
│      Edge Device (Raspberry Pi)     │
│  ┌─────────────────────────────┐    │
│  │   Pi Controller (Docker)    │    │
│  │  - NFC/RFID Reader          │    │
│  │  - GPIO Door Lock           │    │
│  │  - Local SQLite Cache       │    │
│  │  - Voting Filter Algorithm  │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

## 📁 Repository Structure

```
save4223/
├── 📄 README.md                 # This file
├── 📁 docs/                     # Documentation
│   └── ver2plan.md             # V2 Technical Specification
├── 📁 server/                   # Next.js + Supabase (submodule)
│   ├── src/                    # App source code
│   ├── supabase/               # Database migrations
│   └── ...                     # Next.js project
├── 📁 edge/                     # Raspberry Pi controller (TODO)
│   └── docker-compose.yml      # Edge device orchestration
└── 📁 scripts/                  # Deployment scripts (TODO)
```

## 🚀 Quick Start

### Prerequisites

- Node.js 20+
- Docker & Docker Compose
- Supabase CLI
- (For Edge) Raspberry Pi 4 + RFID Reader + Electric Lock

### 1. Clone with Submodules

```bash
git clone --recursive https://github.com/save4223/save4223.git
cd save4223
```

If already cloned without submodules:
```bash
git submodule update --init --recursive
```

### 2. Start Server (Cloud)

```bash
cd server

# Start Supabase
npx supabase start

# Start Next.js dev server
npm install
npm run dev
```

Access:
- **Web App**: http://localhost:3000
- **Supabase Studio**: http://localhost:54323
- **API**: http://localhost:54321

### 3. Start Edge (Raspberry Pi)

```bash
cd edge
docker-compose up -d
```

## 📋 Implementation Roadmap

Based on [V2 Technical Specification](./docs/ver2plan.md):

### Phase 1: Foundation ✅ (Current)
- [x] Project structure setup
- [x] Server submodule configuration
- [x] V2 database schema design

### Phase 2: Core Server (Next)
- [ ] Database migration (Drizzle)
- [ ] Edge API endpoints (`/api/edge/*`)
- [ ] Permission system implementation
- [ ] MinIO object storage integration

### Phase 3: Edge Device
- [ ] Pi controller container
- [ ] RFID reading + Voting filter
- [ ] Offline mode + Sync logic
- [ ] GPIO door lock control

### Phase 4: Polish
- [ ] Admin dashboard
- [ ] Overdue notifications (cron)
- [ ] CCTV snapshot integration
- [ ] Production deployment

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS |
| Backend | Next.js App Router, Supabase |
| Database | PostgreSQL (via Supabase), Drizzle ORM |
| Edge | Raspberry Pi, Python/Node.js, SQLite |
| Storage | MinIO / AWS S3 |
| Deployment | Docker, Docker Compose |

## 📄 License

MIT

## 🤝 Contributing

This is a personal project. For issues and suggestions, please open a GitHub issue.
