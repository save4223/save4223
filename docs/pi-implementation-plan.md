# Smart Cabinet Pi Implementation Plan

## Overview

This document outlines the implementation plan for the Raspberry Pi-based smart tool cabinet controller. The system integrates with the Save4223 backend API to provide authentication, tool tracking, and inventory management.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi (Edge Device)                │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   NFC/QR     │  │    RFID      │  │   Servos     │      │
│  │   Reader     │  │   Reader     │  │   & LEDs     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                 State Machine Controller                 ││
│  └─────────────────────────────────────────────────────────┘│
│                            │                                 │
│  ┌─────────────────────────┼──────────────────────────────┐ │
│  │                         ▼                              │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │ │
│  │  │  Local DB   │  │  API Client │  │   Display   │◀──┼─┼──┐
│  │  │  (SQLite)   │  │   (Sync)    │  │  (Electron/ │   │ │  │
│  │  └─────────────┘  └─────────────┘  │   Browser)   │   │ │  │
│  │                                     └─────────────┘   │ │  │
│  │                                                       │ │  │
│  │  ┌─────────────────────────────────────────────────┐  │ │  │
│  │  │     LOCAL DASHBOARD (Real-time Display)         │  │ │  │
│  │  │  • Shows welcome/instructions when idle         │  │ │  │
│  │  │  • Shows user info when authenticated           │  │ │  │
│  │  │  • Shows item summary after checkout            │  │ │  │
│  │  │  • Updates via WebSocket from main process      │  │ │  │
│  │  └─────────────────────────────────────────────────┘◀─┘ │  │
│  └────────────────────────────────────────────────────────┘   │
│                                                               │
└───────────────────────────────────────────────────────────────┘
                              │
                              │ WebSocket / HTTP
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Save4223 Cloud API                        │
│         (Next.js + Supabase + Drizzle ORM)                   │
└─────────────────────────────────────────────────────────────┘
```

## State Machine

```
                    ┌──────────┐
         ┌─────────│  LOCKED  │◀─────────────────────────┐
         │         └────┬─────┘                          │
         │              │ NFC/QR Valid                   │
         │              ▼                                │
         │         ┌──────────┐   Timeout (30s)         │
         │         │ UNLOCKED │   or Same Card +        │
         │         │          │   All Drawers Closed    │
         │         └────┬─────┘                         │
         │              │                                │
         │              ▼                                │
         │         ┌──────────┐                         │
         └────────▶│ SCANNING │─────────────────────────┘
                   │  (RFID)  │
                   └──────────┘
```

### State Descriptions

| State | Description | LED Indicators |
|-------|-------------|----------------|
| **LOCKED** | Cabinet locked, waiting for NFC/QR authentication | Red (all drawers) |
| **UNLOCKED** | Cabinet open, user can take/return tools | Green (closed drawers), Red (open drawers) |
| **SCANNING** | RFID scanning tools, calculating diff | Yellow |

## API Endpoints (Save4223 Backend)

### 1. Authentication
```http
POST /api/edge/authorize
Authorization: Bearer {EDGE_DEVICE_SECRET_KEY}
Content-Type: application/json

{
  "card_uid": "TEST123",
  "cabinet_id": 1
}
```

**Response:**
```json
{
  "authorized": true,
  "session_id": "uuid",
  "user_id": "uuid",
  "user_name": "John Doe",
  "cabinet_name": "Cabinet A"
}
```

### 2. Sync Session (RFID Diff)
```http
POST /api/edge/sync-session
Authorization: Bearer {EDGE_DEVICE_SECRET_KEY}
Content-Type: application/json

{
  "session_id": "uuid",
  "cabinet_id": 1,
  "user_id": "uuid",
  "rfids_present": ["RFID-001", "RFID-002"]
}
```

**Response:**
```json
{
  "borrowed": [{"rfid": "RFID-003", "item_id": "uuid", "name": "Tool"}],
  "returned": [{"rfid": "RFID-004", "item_id": "uuid", "name": "Tool"}],
  "unexpected": [],
  "session_id": "uuid"
}
```

### 3. Local Sync (Cache)
```http
GET /api/edge/local-sync?cabinet_id=1
Authorization: Bearer {EDGE_DEVICE_SECRET_KEY}
```

**Response:**
```json
{
  "cards": [{"card_uid": "TEST123", "user_id": "uuid", "permissions": [1,2]}],
  "items": [{"rfid_tag": "RFID-001", "item_id": "uuid", "name": "Tool"}]
}
```

## Hardware Components

### NFC/QR Reader (Authentication)
- **Device**: PN532 (NFC) + USB Camera (QR)
- **Purpose**: User authentication
- **Trigger**: Unlock cabinet
- **Output**: Card UID or QR token

### RFID Reader (Tool Tracking)
- **Device**: Multiple MFRC522 readers or UHF RFID
- **Purpose**: Tool inventory scanning
- **Trigger**: After cabinet closes
- **Output**: List of RFID tags present

### Servo Motors (Locks)
- **Device**: PCA9685 + SG90 Servos
- **Purpose**: Lock/unlock drawers
- **Control**: PWM signals via I2C

### Drawer Switches
- **Device**: Magnetic reed switches
- **Purpose**: Detect drawer open/close state
- **Input**: GPIO pins

### LEDs
- **Device**: WS2812B or standard LEDs
- **Purpose**: Status indication
- **Colors**: Red (locked), Green (unlocked), Yellow (scanning)

## File Structure

```
save4223-pi/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py               # Configuration
│   ├── state_machine.py        # State management
│   ├── api_client.py           # HTTP client for API
│   ├── local_db.py             # SQLite local storage
│   ├── local_auth.py           # Local authentication cache
│   ├── sync_worker.py          # Background sync thread
│   ├── transaction_processor.py # RFID diff calculator
│   ├── display_manager.py      # Display/WebSocket manager
│   └── hardware/
│       ├── __init__.py
│       ├── controller.py       # GPIO, servos, LEDs
│       ├── nfc_reader.py       # NFC card reader
│       ├── qr_scanner.py       # QR code scanner
│       └── rfid_reader.py      # RFID tag reader
├── display/                    # Local Dashboard (Electron/Web)
│   ├── package.json
│   ├── main.js                 # Electron main process
│   ├── preload.js              # Electron preload script
│   ├── index.html              # Main HTML
│   ├── styles.css              # Dashboard styles
│   └── renderer.js             # Dashboard UI logic
├── data/
│   ├── local.db                # SQLite database
│   └── tag_mapping.json        # RFID to item mapping
├── tests/
│   ├── test_api_client.py
│   ├── test_state_machine.py
│   └── test_hardware.py
├── requirements.txt
├── config.json                 # Runtime configuration
└── README.md
```

## Local Dashboard (Real-time Display)

The Pi runs a local dashboard display on its connected monitor, providing real-time feedback to users without network latency.

### Why Local Dashboard?

- **Zero Latency**: Updates instantly vs. cloud round-trip
- **Offline Resilient**: Works without internet connection
- **Lower Cost**: No server resources needed for display
- **Better UX**: Immediate visual feedback for card taps

### Dashboard States

| State | Display Content | Trigger |
|-------|-----------------|---------|
| **IDLE** | Welcome screen, registration instructions | Cabinet locked, no user |
| **AUTHENTICATING** | "Please wait..." spinner | Card/QR detected |
| **AUTHENTICATED** | User name, session instructions, countdown | Auth successful |
| **CHECKOUT** | Item summary (borrowed/returned) | Session completed |

### Communication Architecture

```
┌──────────────┐     WebSocket      ┌──────────────┐
│  Main Process │ ◀────────────────▶ │   Display    │
│  (Python)     │   State Updates    │ (Electron)   │
└──────────────┘                    └──────────────┘
       │                                     │
       │ SQLite Events                       │ Render UI
       ▼                                     ▼
┌──────────────┐                    ┌──────────────┐
│  Local DB    │                    │   Monitor    │
│  (SQLite)    │                    │  (HDMI/DSI)  │
└──────────────┘                    └──────────────┘
```

### Implementation Options

**Option 1: Electron App (Recommended)**
- Full desktop app with Node.js backend
- Direct WebSocket to main Python process
- Easy to style with modern CSS
- Can run in kiosk mode

**Option 2: Web Browser + Local Server**
- Python Flask/FastAPI serves web page
- Browser runs in fullscreen/kiosk mode
- Simpler stack, easier to debug

**Option 3: PyQt/PySide GUI**
- Native Python GUI
- No JavaScript/Web stack
- Harder to style, less flexible

### Recommended: Electron Approach

```javascript
// Main process (Node.js)
const { WebSocket } = require('ws');
const ws = new WebSocket('ws://localhost:8765');

ws.on('message', (data) => {
  const event = JSON.parse(data);
  // Update window with new state
  mainWindow.webContents.send('state-update', event);
});

// Renderer process (UI)
ipcRenderer.on('state-update', (event, data) => {
  updateDashboard(data);
});
```

### WebSocket Protocol

```typescript
interface StateUpdate {
  type: 'STATE_CHANGE' | 'AUTH_SUCCESS' | 'AUTH_FAILURE' | 
         'ITEM_SUMMARY' | 'ERROR';
  state: 'LOCKED' | 'AUTHENTICATING' | 'UNLOCKED' | 'SCANNING';
  user?: {
    id: string;
    email: string;
    full_name?: string;
  };
  itemSummary?: {
    borrowed: Array<{tag: string, name: string}>;
    returned: Array<{tag: string, name: string}>;
  };
  error?: string;
}
```

## Implementation Phases

### Phase 1: Core Framework (Week 1)
1. Set up project structure
2. Implement state machine
3. Create configuration module
4. Add logging infrastructure

### Phase 2: API Integration (Week 1-2)
1. Implement API client with retry logic
2. Add authentication endpoint integration
3. Create sync session handling
4. Implement local caching

### Phase 3: Hardware Integration (Week 2)
1. NFC/QR reader integration
2. Servo motor control
3. Drawer switch monitoring
4. LED status indicators

### Phase 4: RFID & Transactions (Week 3)
1. RFID reader integration
2. Tag diff calculation
3. Transaction processing
4. Local database operations

### Phase 5: Sync & Offline (Week 3-4)
1. Background sync worker
2. Offline mode support
3. Conflict resolution
4. Data persistence

### Phase 6: Local Dashboard (Week 4-5)
1. Set up Electron app structure
2. Create WebSocket server in main process
3. Build dashboard UI components
4. Implement state update protocol
5. Add kiosk mode for production
6. Style with DaisyUI/theme matching

### Phase 7: Testing & Polish (Week 5-6)
1. End-to-end testing
2. Error handling
3. Performance optimization
4. Documentation

## Key Design Decisions

### 1. Local-First Architecture
- SQLite database for local storage
- Background sync to cloud
- Works offline, syncs when online
- Cached authentication for fast unlock

### 2. Stateless Sessions
- Each session is independent
- Session ID generated per unlock
- RFID diff calculated at close time
- Transactions recorded atomically

### 3. Robust Error Handling
- Network failures don't block operation
- Hardware failures trigger safe state
- Automatic retry with exponential backoff
- Clear LED feedback for errors

### 4. Security
- Edge device secret key for API auth
- Card UID validation
- Session timeout (30s)
- No sensitive data stored locally

## Configuration

```python
# config.py
SERVER_URL = "http://100.83.123.68:3000"
EDGE_DEVICE_SECRET_KEY = "edge_device_secret_key"
CABINET_ID = 1

# Hardware pins
SERVO_I2C_ADDRESS = 0x40
NFC_SPI_DEVICE = 0
RFID_SPI_DEVICES = [0, 1, 2]
DRAWER_SWITCH_PINS = [17, 27, 22, 23]
LED_PIN = 18

# Timing
SESSION_TIMEOUT = 30  # seconds
RFID_SCAN_COUNT = 10
SYNC_INTERVAL = 60    # seconds
```

## Testing Strategy

1. **Unit Tests**: Mock hardware, test state machine
2. **Integration Tests**: Test API client with staging server
3. **Hardware Tests**: Individual component testing
4. **E2E Tests**: Full workflow with test tags

## Deployment

1. Install dependencies: `pip install -r requirements.txt`
2. Configure `config.json` with cabinet ID and API key
3. Run database migration: `python -m src.local_db migrate`
4. Start service: `python -m src.main`
5. Enable auto-start: `sudo systemctl enable cabinet`

## References

- Original code: https://github.com/year3-project/tool-cabinet-pi
- API Documentation: `/home/ada/save4223/server/API_TESTING.md`
- Database Schema: `/home/ada/save4223/server/src/db/schema.ts`
