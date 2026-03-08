# Raspberry Pi - Server Sync Implementation Plan

## Overview
实现树莓派与服务器之间的 HTTPS 通信和数据同步，确保硬件组装完成后可立即部署。

## Current Architecture Analysis

### Server Side (Existing)
- `/api/edge/authorize` - NFC 卡验证
- `/api/edge/sync-session` - 会话同步 (RFID diff 计算)
- `/api/edge/local-sync` - 离线缓存数据获取
- `/api/edge/pair-card` - NFC 卡配对

### Cabinet Pi Side (Existing)
- `main.py` - 主控制器 (状态机: LOCKED → AUTHENTICATING → UNLOCKED → SCANNING)
- `api_client.py` - HTTP 客户端
- `local_db.py` - SQLite 离线数据库
- `sync_worker.py` - 后台同步
- `hardware/` - 硬件控制模块 (当前为空)

## Phase 1: HTTPS Communication Layer

### 1.1 Server HTTPS Setup
**Files:**
- `server/docker-compose.yml` (新增)
- `server/nginx/nginx.conf` (新增)
- `server/.env.production` (新增)

**Implementation:**
```yaml
# docker-compose.yml
services:
  app:
    # 现有 Next.js 应用
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
```

**Self-signed certificate generation for Pi:**
```bash
# 在服务器上生成证书
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/server.key -out ssl/server.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/CN=server.local"
```

### 1.2 Pi HTTPS Client
**File:** `cabinet-pi/src/api_client.py` (修改)

**Changes:**
- 添加 SSL/TLS 支持
- 配置证书验证 (使用自签名证书)
- 添加连接重试和超时机制

```python
class APIClient:
    def __init__(self, base_url: str, edge_secret: str,
                 cert_path: Optional[str] = None):
        self.session = requests.Session()
        if cert_path:
            self.session.verify = cert_path  # 自签名证书路径
        else:
            self.session.verify = True  # 系统证书
```

## Phase 2: Hardware Abstraction Layer

### 2.1 Hardware Interface Definition
**File:** `cabinet-pi/src/hardware/base.py` (新增)

```python
from abc import ABC, abstractmethod
from typing import List, Optional

class HardwareInterface(ABC):
    """Abstract hardware interface for testability."""

    @abstractmethod
    def read_nfc_or_qr(self, timeout: float = 30) -> Optional[str]:
        """Read NFC card or QR code."""
        pass

    @abstractmethod
    def read_rfid_tags(self) -> List[str]:
        """Read all RFID tags in cabinet."""
        pass

    @abstractmethod
    def unlock_all(self) -> None:
        """Unlock all drawers."""
        pass

    @abstractmethod
    def lock_all(self) -> None:
        """Lock all drawers."""
        pass

    @abstractmethod
    def is_drawer_open(self, drawer_id: int) -> bool:
        """Check if specific drawer is open."""
        pass

    @abstractmethod
    def are_all_drawers_closed(self) -> bool:
        """Check if all drawers are closed."""
        pass

    @abstractmethod
    def set_led(self, index: int, color: str) -> None:
        """Set LED color (red/green/yellow/off)."""
        pass

    @abstractmethod
    def set_all_leds(self, color: str) -> None:
        """Set all LEDs to same color."""
        pass

    @abstractmethod
    def beep_success(self) -> None:
        """Success beep pattern."""
        pass

    @abstractmethod
    def beep_error(self) -> None:
        """Error beep pattern."""
        pass

    @abstractmethod
    def beep_warning(self) -> None:
        """Warning beep pattern."""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Cleanup GPIO/resources."""
        pass
```

### 2.2 Mock Hardware Implementation (for testing)
**File:** `cabinet-pi/src/hardware/mock.py` (新增)

模拟硬件用于开发和测试，无需真实硬件。

```python
class MockHardware(HardwareInterface):
    """Mock hardware for development without physical components."""

    def __init__(self):
        self._drawer_states = {i: False for i in range(4)}  # False = closed
        self._led_states = {i: 'off' for i in range(4)}
        self._mock_tags = ['RFID-001', 'RFID-002', 'RFID-003']

    def read_nfc_or_qr(self, timeout: float = 30) -> Optional[str]:
        # 模拟键盘输入或从文件读取
        # 开发时可以手动输入卡号
        print("\n[MOCK] Enter card UID (or press Enter to simulate timeout):")
        import select
        import sys

        ready, _, _ = select.select([sys.stdin], [], [], timeout)
        if ready:
            return sys.stdin.readline().strip()
        return None
```

### 2.3 Real Hardware Implementation
**File:** `cabinet-pi/src/hardware/raspberry_pi.py` (新增)

真实硬件实现，基于现有代码中的配置：
- PN532 NFC 模块 (SPI)
- RC522 RFID 模块 (多路 SPI)
- PCA9685 伺服控制器 (I2C)
- GPIO 门磁检测
- WS2812 LED 灯带

## Phase 3: Data Sync Protocol

### 3.1 Bidirectional Sync Flow

```
┌─────────────┐                    ┌─────────────┐
│   Pi (Edge) │  ─── HTTPS ───▶   │   Server    │
│             │  ◀── HTTPS ───    │             │
└─────────────┘                    └─────────────┘

Sync Data:
1. Pi → Server: Session events (BORROW/RETURN)
2. Pi → Server: RFID scan snapshots
3. Server → Pi: User permissions cache
4. Server → Pi: Item inventory updates
5. Server → Pi: Access control changes
```

### 3.2 Enhanced Sync Worker
**File:** `cabinet-pi/src/sync_worker.py` (增强)

**新增功能:**
- 增量同步 (timestamp-based)
- 冲突解决策略
- 批量同步优化
- 网络状态监控

```python
class EnhancedSyncWorker(threading.Thread):
    """Enhanced sync with bidirectional data flow."""

    def __init__(self, local_db, api_client, config):
        super().__init__(daemon=True)
        self.sync_types = {
            'sessions': self._sync_sessions,
            'permissions': self._sync_permissions,
            'inventory': self._sync_inventory,
        }

    def _sync_permissions(self):
        """Fetch latest user permissions and access rules."""
        server_data = self.api.local_sync(self.config['cabinet_id'])
        self.local_db.update_permissions_cache(server_data)

    def _sync_inventory(self):
        """Sync item status changes from server."""
        # 获取服务器上更新的物品状态
        last_sync = self.local_db.get_last_inventory_sync()
        changes = self.api.get_inventory_changes(since=last_sync)
        self.local_db.apply_inventory_changes(changes)
```

### 3.3 New Server APIs
**Files:**
- `server/src/app/api/edge/inventory/route.ts` (新增)
- `server/src/app/api/edge/health/route.ts` (新增)

```typescript
// GET /api/edge/inventory?since=timestamp
// 返回自上次同步以来的物品状态变化

// POST /api/edge/batch-sync
// 批量同步多个会话
```

## Phase 4: Configuration & Deployment

### 4.1 Production Configuration
**File:** `cabinet-pi/config.production.json`

```json
{
  "server_url": "https://save4223.local:8443",
  "edge_secret": "${EDGE_SECRET}",
  "cabinet_id": 1,
  "db_path": "/var/lib/cabinet/local.db",
  "ssl": {
    "verify": true,
    "cert_path": "/etc/cabinet/ssl/server.crt"
  },
  "hardware": {
    "mode": "raspberry_pi",
    "nfc": {
      "type": "pn532",
      "interface": "spi",
      "port": 0
    },
    "rfid": {
      "type": "rc522",
      "ports": [0, 1, 2, 3],
      "multiplexer": true
    },
    "servo": {
      "type": "pca9685",
      "i2c_address": "0x40",
      "frequency": 50
    }
  }
}
```

### 4.2 Docker Setup for Pi
**File:** `cabinet-pi/Dockerfile`

```dockerfile
FROM python:3.11-slim-bookworm

# 安装系统依赖 (包含 GPIO, SPI, I2C)
RUN apt-get update && apt-get install -y \
    gcc \
    libgpiod2 \
    python3-libgpiod \
    spi-tools \
    i2c-tools \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY src/ ./src/
COPY config.json /etc/cabinet/config.json

# 设备访问权限
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
```

### 4.3 Docker Compose (Pi Side)
**File:** `cabinet-pi/docker-compose.yml`

```yaml
version: '3.8'

services:
  cabinet:
    build: .
    privileged: true  # 访问硬件需要
    volumes:
      - ./data:/var/lib/cabinet
      - ./ssl:/etc/cabinet/ssl
      - /dev/gpiomem:/dev/gpiomem
      - /dev/spidev0.0:/dev/spidev0.0
      - /dev/spidev0.1:/dev/spidev0.1
      - /dev/i2c-1:/dev/i2c-1
    environment:
      - CABINET_SERVER_URL=https://save4223.local:8443
      - CABINET_EDGE_SECRET=${EDGE_SECRET}
      - CABINET_ID=1
    restart: unless-stopped
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

## Phase 5: Testing & Validation

### 5.1 Test Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| 在线授权 | NFC 验证通过，立即开锁 |
| 离线授权 | 使用本地缓存验证 |
| 在线同步 | 会话立即同步到服务器 |
| 离线同步 | 会话排队，网络恢复后自动同步 |
| 冲突解决 | 服务器状态为准，本地标记异常 |
| 硬件故障 | 进入降级模式，记录错误日志 |

### 5.2 Monitoring & Logging
**File:** `cabinet-pi/src/monitoring.py` (新增)

- 系统健康检查
- 网络状态监控
- 硬件状态报告
- 错误告警机制

## Implementation Checklist

### Server Side
- [ ] HTTPS 配置 (nginx + SSL 证书)
- [ ] 批量同步 API (`/api/edge/batch-sync`)
- [ ] 库存变更 API (`/api/edge/inventory`)
- [ ] 健康检查 API (`/api/edge/health`)
- [ ] WebSocket 支持 (可选，用于实时通知)

### Cabinet Pi Side
- [ ] HTTPS 客户端 (证书验证)
- [ ] 硬件抽象层 (base.py)
- [ ] Mock 硬件实现 (开发测试)
- [ ] 真实硬件实现 (Raspberry Pi)
- [ ] 增强同步 worker
- [ ] 监控和日志系统
- [ ] Docker 配置

### Deployment
- [ ] SSL 证书生成脚本
- [ ] 生产环境配置模板
- [ ] 自动部署脚本
- [ ] 系统服务配置 (systemd)

## Hardware Wiring Reference

### NFC Module (PN532)
```
PN532    Raspberry Pi
-------    ------------
VCC  →   3.3V (Pin 1)
GND  →   GND  (Pin 6)
SCK  →   SCLK (Pin 23)
MISO →   MISO (Pin 21)
MOSI →   MOSI (Pin 19)
SS   →   GPIO8 (Pin 24)
```

### RFID Multiplexer (4x RC522)
```
使用 74HC4052 多路复用器共享 SPI 总线
RC522_1 → Port 0
RC522_2 → Port 1
RC522_3 → Port 2
RC522_4 → Port 3
```

### Servo Controller (PCA9685)
```
PCA9685  Raspberry Pi
--------  ------------
VCC    →  5V   (Pin 2)
GND    →  GND  (Pin 6)
SCL    →  SCL  (Pin 5)
SDA    →  SDA  (Pin 3)
```

## Next Steps

1. **立即开始:** Phase 1 (HTTPS) - 不依赖硬件
2. **并行开发:** Phase 2 (Mock Hardware) - 使用模拟硬件开发
3. **硬件就绪后:** 切换到真实硬件实现
4. **测试验证:** 完整集成测试

## Notes

- 所有 HTTP 通信必须改为 HTTPS
- 自签名证书需要预装到 Pi
- 支持离线操作是核心需求
- 状态机设计确保操作原子性
- 本地数据库保证数据持久化
