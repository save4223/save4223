# Save4223 - Smart Lab Inventory System

[![GitHub](https://img.shields.io/badge/GitHub-save4223-blue)](https://github.com/save4223/save4223)

**ISDN Smart Inventory & Tool Cabinet (V2)**

A cloud-edge hybrid inventory management system for labs and workshops. Features real-time RFID tracking, session-based auditing, offline-capable edge devices, automated overdue notifications, and **AI-powered tool recommendations**.

## Features

- **Real-time RFID Tracking** - Track tools as they're borrowed and returned
- **Session-based Auditing** - Complex transaction tracking with open/close snapshots
- **Offline-capable Edge Devices** - Raspberry Pi controllers with SQLite cache
- **NFC Card Authentication** - Quick access with NFC cards
- **AI Project Assistant** - Describe your project, get personalized tool recommendations
- **Multi-factor Reranking** - Semantic, availability, popularity, and LLM-based scoring

## Architecture

```
┌─────────────────────────────────────┐
│         Cloud Server (Linux)        │
│  ┌─────────────────────────────┐    │
│  │      Next.js 15 App         │    │
│  │  - Web Dashboard            │    │
│  │  - REST API                 │    │
│  │  - Admin Panel              │    │
│  │  - AI Recommendation Engine │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │    PostgreSQL (Supabase)    │    │
│  │  - User Profiles            │    │
│  │  - Inventory Data           │    │
│  │  - Session Audit Logs       │    │
│  │  - pgvector Embeddings      │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │   MinIO (Object Storage)    │    │
│  │  - Tool Images              │    │
│  │  - CCTV Snapshots           │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │      Ollama / OpenAI        │    │
│  │  - Embedding Generation     │    │
│  │  - LLM Reranking            │    │
│  │  - Recommendation Text      │    │
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

## Repository Structure

```
save4223/
├── README.md                 # This file
├── CLAUDE.md                 # Development guide for Claude Code
├── docs/                     # Documentation
│   ├── ver2plan.md          # V2 Technical Specification
│   └── tool-recommendation-plan.md  # RAG Recommendation PRD
├── server/                   # Next.js + Supabase (submodule)
│   ├── src/
│   │   ├── app/             # Pages and API routes
│   │   ├── lib/llm/         # LLM provider abstraction
│   │   ├── services/        # Business logic (embeddings, recommendations)
│   │   └── test/            # Test suites
│   ├── supabase/            # Database migrations
│   └── ...                  # Next.js project
├── cabinet-pi/               # Raspberry Pi Python controller
│   ├── src/                 # Controller code
│   └── display/             # Electron dashboard
├── edge/                     # Docker compose for Pi deployment
└── scripts/                  # Deployment scripts
```

## Quick Start

### Prerequisites

- Node.js 20+
- Docker & Docker Compose
- Supabase CLI
- (For AI Features) Ollama or OpenAI API key
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

# Install dependencies
npm install

# Seed database (includes pgvector extension)
npm run db:seed

# Start Next.js dev server
npm run dev
```

Access:
- **Web App**: http://localhost:3000
- **Supabase Studio**: http://localhost:54323
- **AI Assistant**: http://localhost:3000/user/assistant

### 3. Enable AI Features (Optional)

For local LLM (recommended for privacy):
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull required models
ollama pull nomic-embed-text  # Embedding model
ollama pull llama3.2          # Chat model
```

For OpenAI (alternative):
```bash
# Add to server/.env.local
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

Generate embeddings:
```bash
curl -X POST http://localhost:3000/api/admin/embeddings \
  -H "Content-Type: application/json" \
  -d '{"action": "generate-missing"}'
```

### 4. Start Edge (Raspberry Pi)

```bash
cd edge
docker-compose up -d
```

## AI Recommendation Engine

The system includes a RAG-based recommendation engine that helps users find the right tools for their projects.

### How it Works

1. **User Input** - User describes their project in natural language
2. **Vector Retrieval** - System finds similar tools using pgvector
3. **Multi-factor Reranking** - Combines multiple signals:
   - Semantic similarity (25%)
   - Availability score (20%)
   - Category relevance (15%)
   - Popularity score (10%)
   - LLM rerank score (30%)
4. **Explanation Generation** - LLM generates personalized recommendations

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/user/recommendations` | POST | Get tool recommendations |
| `/api/admin/embeddings` | GET | Get embedding statistics |
| `/api/admin/embeddings` | POST | Generate/regenerate embeddings |

### Running Tests

```bash
cd server

# Full test suite (requires LLM)
npm run test:recommendations

# Fast test (skip LLM reranking)
npm run test:recommendations:fast

# Verbose output
npm run test:recommendations:verbose
```

## Implementation Status

Based on [V2 Technical Specification](./docs/ver2plan.md):

### Phase 1: Foundation
- [x] Project structure setup
- [x] Server submodule configuration
- [x] V2 database schema design

### Phase 2: Core Server
- [x] Database migration (Drizzle)
- [x] Edge API endpoints (`/api/edge/*`)
- [x] Permission system implementation
- [x] MinIO object storage integration

### Phase 3: AI Features
- [x] pgvector extension enabled
- [x] LLM provider abstraction (Ollama, OpenAI)
- [x] Embedding service
- [x] Multi-factor reranking engine
- [x] Recommendation API
- [x] AI Assistant UI
- [x] Testing framework with evaluation metrics

### Phase 4: Edge Device
- [ ] Pi controller container
- [ ] RFID reading + Voting filter
- [ ] Offline mode + Sync logic
- [ ] GPIO door lock control

### Phase 5: Polish
- [x] Admin dashboard
- [ ] Overdue notifications (cron)
- [ ] CCTV snapshot integration
- [ ] Production deployment

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React, TypeScript, Tailwind CSS, DaisyUI |
| Backend | Next.js App Router, Supabase |
| Database | PostgreSQL (via Supabase), Drizzle ORM, pgvector |
| AI/ML | Ollama (local) / OpenAI, RAG pipeline |
| Edge | Raspberry Pi, Python/Node.js, SQLite |
| Storage | MinIO / AWS S3 |
| Deployment | Docker, Docker Compose |

## License

MIT

## Contributing

This is a personal project. For issues and suggestions, please open a GitHub issue.
