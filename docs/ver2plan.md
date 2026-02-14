
# Smart Lab Inventory System (V2)

**Technical Specification & Refactoring Plan**

| **Metadata**     | **Details**                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------ |
| **Project Name** | ISDN Smart Inventory & Tool Cabinet                                                                    |
| **Version**      | 2.0.0 (Refactor)                                                                                       |
| **Status**       | **Approved for Development**                                                                           |
| **Tech Stack**   | Next.js 15, Supabase (PostgreSQL), Drizzle ORM, Docker, Raspberry Pi (Edge), MinIO/S3 (Object Storage) |

---

## 1. Executive Summary

The V2 refactor aims to resolve critical stability and logic issues identified in V1. The new architecture introduces **Edge Computing** to minimize latency, a **Session-Based Database Schema** to accurately handle mixed borrow/return transactions, and a robust **Permission System** for restricted equipment. The entire system will be containerized via Docker for consistent deployment across cloud servers and Raspberry Pi edge devices.

### Key Architectural Changes

1. **Session-Based Auditing:** Replaces simple state overwrites with a "Session (Parent) + Transaction (Child)" model to track complex user behaviors (borrowing and returning simultaneously).
    
2. **Edge-First Logic:** The Raspberry Pi runs a local database (SQLite) and logic engine, synchronizing with the cloud asynchronously. This ensures the cabinet opens immediately and works offline.
    
3. **Advanced Permissions:** Introduces a default-open policy with specific "Restricted" flags for high-value cabinets, requiring approval workflows.
    
4. **Object Storage:** Integration with S3/MinIO to store tool images and transaction evidence (CCTV/Audit snapshots).
    

---

## 2. Database Schema (PostgreSQL)

### 2.1 Identity & Access Control

Refined to support the new "Restricted Cabinet" logic.

SQL

```
-- [User Profiles] Extended user data linked to Supabase Auth
CREATE TABLE profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email text NOT NULL,
  full_name text,
  role varchar(20) DEFAULT 'USER' CHECK (role IN ('ADMIN', 'MANAGER', 'USER')),
  created_at timestamptz DEFAULT now()
);

-- [Locations] Defines physical storage units
CREATE TABLE locations (
  id serial PRIMARY KEY,
  name varchar(100) NOT NULL, -- e.g., "Cabinet A", "Drawer 1"
  type varchar(20) CHECK (type IN ('CABINET', 'DRAWER', 'BIN')),
  parent_id integer REFERENCES locations(id),
  
  -- [NEW] Access Control Flag
  is_restricted boolean DEFAULT false, -- If false, accessible by all. If true, requires explicit permission.
  
  created_at timestamptz DEFAULT now()
);

-- [Access Requests/Permissions] Managed access for restricted locations
CREATE TABLE access_permissions (
  id serial PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  location_id integer REFERENCES locations(id) ON DELETE CASCADE,
  
  -- Workflow Status
  status varchar(20) DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'REVOKED')),
  
  -- Time-based Access Control
  valid_from timestamptz,
  valid_until timestamptz, -- NULL = Indefinite access
  
  request_reason text,
  approved_by uuid REFERENCES auth.users(id),
  created_at timestamptz DEFAULT now()
);

-- [Physical Cards] NFC/RFID Card binding
CREATE TABLE user_cards (
  id serial PRIMARY KEY,
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  card_uid varchar(50) UNIQUE NOT NULL,
  is_active boolean DEFAULT true,
  last_used_at timestamptz,
  created_at timestamptz DEFAULT now()
);
```

### 2.2 Inventory Definition

Updated to support overdue tracking and object storage images.

SQL

```
-- [Item Types] SKU/Category Definitions
CREATE TABLE item_types (
  id serial PRIMARY KEY,
  name varchar(100) NOT NULL,
  category varchar(50), -- 'TOOL', 'CONSUMABLE', 'DEVICE'
  description text,
  
  -- [NEW] Object Storage Reference
  image_url text, 
  
  -- [NEW] Default Borrow Rules
  max_borrow_duration interval DEFAULT '7 days', 
  
  total_quantity integer DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

-- [Items] Individual physical instances
CREATE TABLE items (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  item_type_id integer REFERENCES item_types(id),
  rfid_tag varchar(100) UNIQUE NOT NULL,
  
  -- Current Status
  status varchar(20) DEFAULT 'AVAILABLE' CHECK (status IN ('AVAILABLE', 'BORROWED', 'MISSING', 'MAINTENANCE')),
  home_location_id integer REFERENCES locations(id),
  
  -- [NEW] Real-time Ownership & Due Date
  current_holder_id uuid REFERENCES auth.users(id),
  due_at timestamptz, -- Calculated at borrow time: now() + max_borrow_duration
  
  last_overdue_notice_sent_at timestamptz,
  updated_at timestamptz DEFAULT now()
);
```

### 2.3 Session Engine (The Core V2 Feature)

Solves the "Mixed Transaction" and "Audit" issues.

SQL

```
-- [Parent] Cabinet Session: One complete interaction (Open -> Close)
CREATE TABLE cabinet_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cabinet_id integer REFERENCES locations(id),
  user_id uuid REFERENCES auth.users(id),
  
  start_time timestamptz DEFAULT now(),
  end_time timestamptz,
  
  status varchar(20) DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'COMPLETED', 'TIMEOUT', 'FORCE_CLOSED')),
  
  -- [Audit] Raw snapshots for debugging algorithm failures
  snapshot_start_rfids jsonb, 
  snapshot_end_rfids jsonb, 
  
  created_at timestamptz DEFAULT now()
);

-- [Child] Inventory Transactions: Atomic events calculated from the session
CREATE TABLE inventory_transactions (
  id serial PRIMARY KEY,
  session_id uuid REFERENCES cabinet_sessions(id) ON DELETE CASCADE,
  
  item_id uuid REFERENCES items(id),
  user_id uuid REFERENCES auth.users(id), -- Redundant but useful for quick queries
  
  action_type varchar(20) CHECK (action_type IN ('BORROW', 'RETURN', 'MISSING_UNEXPECTED')),
  
  -- [Evidence] Link to S3/MinIO image of the transaction event
  evidence_image_path text,
  
  timestamp timestamptz DEFAULT now()
);
```

---

## 3. API Specification (Next.js App Router)

### 3.1 Edge Device APIs (For Raspberry Pi)

_Authentication Strategy: API Key / Bearer Token specific to the Cabinet Device._

#### `POST /api/edge/authorize`

- **Purpose:** Determine if a user can open the door.
    
- **Logic:**
    
    1. Lookup user by `card_uid`.
        
    2. Check `locations.is_restricted` for the requested cabinet.
        
    3. If restricted, check `access_permissions` for `APPROVED` status AND `valid_until > now()`.
        
- **Response:** `{ "authorized": true, "session_id": "uuid...", "user_name": "Vicky" }` or `403 Forbidden`.
    

#### `POST /api/edge/sync-session`

- **Purpose:** Finalize a transaction after the door closes.
    
- **Payload:**
    
    JSON
    
    ```
    {
      "session_id": "uuid...",
      "end_rfids": ["tag_a", "tag_b"],
      "evidence_image": "base64_string..." (optional, enables immediate upload)
    }
    ```
    
- **Server-Side Processing (Transactional):**
    
    1. Update `cabinet_sessions` (set `end_time`, `snapshot_end`).
        
    2. **Diff Algorithm:** Compare `snapshot_start` vs `end_rfids`.
        
        - Missing = **BORROW**
            
        - New = **RETURN**
            
    3. Insert rows into `inventory_transactions`.
        
    4. Update `items`:
        
        - If Borrow: Set `status='BORROWED'`, `holder=user`, `due_at = now() + type.duration`.
            
        - If Return: Set `status='AVAILABLE'`, `holder=null`, `due_at=null`.
            
    5. Trigger Email Notification.
        

#### `GET /api/edge/local-sync`

- **Purpose:** Pi pulls this every 10 mins to cache permissions locally (Offline Mode).
    
- **Response:** List of active Card UIDs and their permission levels.
    

### 3.2 Frontend/Admin APIs

#### `POST /api/access-request`

- **Purpose:** User requests access to a restricted cabinet.
    
- **Logic:** Creates a `PENDING` row in `access_permissions`.
    

#### `GET /api/admin/overdue-items`

- **Purpose:** List all items where `due_at < now()`.
    

---

## 4. Edge Logic (Raspberry Pi & Docker)

The Pi will run a **Docker Container** (Python or Node.js) interacting with hardware.

### 4.1 Local State Machine

1. **IDLE:** Poll NFC reader.
    
2. **AUTH:** Read Card -> Check Local DB (SQLite) -> If valid, unlock GPIO.
    
3. **SESSION_START:**
    
    - Record `start_time`.
        
    - Read all current RFID tags -> Save as `Start Snapshot`.
        
    - Upload `ACTIVE` session status to Cloud (if online).
        
4. **MONITOR:** Detect door sensor (Open -> Closed).
    
5. **PROCESSING (The Filter Algorithm):**
    
    - Wait for door locked signal.
        
    - **Voting Mechanism:** Scan RFIDs for 2.0 seconds (e.g., 10 rounds).
        
    - **Filter:** Only accept tags present in >80% of scans (eliminates ghost reads).
        
    - **RSSI Filter:** Ignore tags with Signal < -75dBm (eliminates leakage).
        
6. **SYNC:** Send `End Snapshot` to `/api/edge/sync-session`.
    

### 4.2 Offline Capability

- **Local DB (SQLite):** Stores `users_cache` and `pending_sessions`.
    
- If Wi-Fi is down during Step 6, save the session payload to `pending_sessions`.
    
- A background "Retry Worker" attempts to upload pending sessions every minute until successful.
    

---

## 5. Automated Tasks (Cron Jobs)

### 5.1 Overdue Monitor

- **Frequency:** Hourly.
    
- **Query:**
    
    SQL
    
    ```
    SELECT * FROM items 
    WHERE status = 'BORROWED' 
    AND due_at < NOW() 
    AND (last_overdue_notice_sent_at IS NULL OR last_overdue_notice_sent_at < NOW() - interval '24 hours')
    ```
    
- **Action:** Send email template "Item Overdue" to `profiles.email`. Update `last_overdue_notice_sent_at`.
    

## 6. Deployment & Infrastructure Strategy (Cloud-Edge Hybrid)

To ensure performance, scalability, and offline resilience, the system adopts a **Split-Docker Architecture**. The heavy business logic and UI (Next.js) reside on a powerful Linux Server, while the Raspberry Pi runs a lightweight, purpose-built container for hardware control.

### 6.1 Architecture Topology

The system is divided into two distinct Docker environments communicating via HTTP/REST.

|**Environment**|**Cloud / Linux Server (Central Hub)**|**Edge / Raspberry Pi (Satellite)**|
|---|---|---|
|**Primary Role**|User Interface, API, Primary Database, Object Storage|Hardware Control (RFID/Lock), Offline Auth, Caching|
|**Compute Load**|High (SSR, Image Processing, Data Aggregation)|Low (Serial I/O, Signal Filtering, GPIO)|
|**Connectivity**|Public/LAN IP (Static recommended)|DHCP (Client-only, no inbound ports required)|

### 6.2 Service Definition (Docker Compose)

#### A. Server-Side Composition (Linux Host)

Runs the core application stack.

- **Context:** Located at `./server/docker-compose.yml`
    
- **Services:**
    
    1. **`app`**: Next.js 15 application (Node.js runtime). Exposes Port 3000.
        
    2. **`db`**: PostgreSQL 15 (Primary Data Store).
        
    3. **`object-store`**: MinIO (S3-compatible storage for tool images & audit snapshots).
        

YAML

```
# server/docker-compose.yml
version: '3.8'
services:
  inventory-app:
    build: ../app
    restart: always
    ports:
      - "3000:3000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/inventory
      - S3_ENDPOINT=http://minio:9000
    depends_on:
      - db
      - minio

  db:
    image: postgres:15-alpine
    volumes:
      - pg_data:/var/lib/postgresql/data

  minio:
    image: minio/minio
    command: server /data
    ports:
      - "9000:9000"
      - "9001:9001" # Console
```

#### B. Edge-Side Composition (Raspberry Pi)

Runs the hardware controller. This container is designed to be "stateless" regarding code (easy updates) but "stateful" regarding cache (offline tolerance).

- **Context:** Located at `./edge/docker-compose.yml`
    
- **Services:**
    
    1. **`controller`**: Python/Node.js script handling the Event Loop (RFID Scan -> Filter -> Sync).
        
- **Hardware Access:** Requires mapping `/dev` devices into the container.
    

YAML

```
# edge/docker-compose.yml
version: '3.8'
services:
  pi-controller:
    build: . 
    restart: always
    privileged: true # Required for GPIO and USB Serial access
    # Alternatively, use specific device mapping for better security:
    # devices:
    #   - "/dev/ttyUSB0:/dev/ttyUSB0"
    #   - "/dev/gpiomem:/dev/gpiomem"
    
    volumes:
      - ./local_data:/app/data # Persist SQLite cache across container restarts
    
    environment:
      - SERVER_URL=http://<LINUX_SERVER_IP>:3000
      - CABINET_ID=CABINET_01
      - API_SECRET=edge_device_secret_key
      - SYNC_INTERVAL_MS=5000
```

### 6.3 Communication Protocol

The Raspberry Pi acts as the **Active Client**. It initiates all connections; the Server never initiates a connection to the Pi. This bypasses the need for static IPs or firewall configuration on the Pi side.

1. **Heartbeat & Config Pull (Polling):**
    
    - The Pi polls `GET /api/edge/local-sync` every 5-10 minutes.
        
    - **Data:** Updates local SQLite with valid Card UIDs and Permission tables.
        
    - **Purpose:** Ensures the Pi can authorize users even if the Server goes down 1 minute later.
        
2. **Session Push (Event-Driven):**
    
    - The Pi POSTs to `/api/edge/sync-session` immediately after a user transaction (door close).
        
    - **Retry Logic:** If the Server is unreachable (500/Timeout), the payload is saved to the local SQLite `pending_queue`. A background worker retries the upload exponentially until successful.
        
3. **Security:**
    
    - **Transport:** HTTPs (recommended if Server has domain) or HTTP (internal LAN).
        
    - **Auth:** Bearer Token mechanism. The Pi includes `Authorization: Bearer <API_SECRET>` in headers.

## 7. Migration & Implementation Steps

1. **Setup Object Storage:** Configure MinIO (local) or AWS S3 bucket.
    
2. **Database Migration:** Run Drizzle migrations to create the new V2 tables defined in Section 2.
    
3. **Edge Logic:** Write the Python/Node script implementing the "Voting" and "Offline" logic.
    
4. **API Dev:** Implement the `sync-session` endpoint with the transactional Diff logic.
    
5. **Frontend Update:** Refactor the "My Holdings" page to query the `items` table directly (instead of the old holdings table).