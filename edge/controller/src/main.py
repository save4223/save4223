"""
Edge Controller Main Entry Point

State Machine:
1. IDLE: Poll NFC reader
2. AUTH: Validate card → Unlock door
3. SESSION_START: Record start snapshot
4. MONITOR: Wait for door close
5. PROCESSING: Voting scan → Filter → Sync
6. SYNC: Upload to cloud server
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EdgeController:
    """Main edge controller managing hardware and cloud sync"""
    
    def __init__(self):
        self.running = False
        self.current_session = None
        
    async def start(self):
        """Start the controller"""
        logger.info("🚀 Edge Controller starting...")
        self.running = True
        
        # TODO: Initialize hardware (RFID, GPIO)
        # TODO: Initialize local database
        # TODO: Start heartbeat/sync workers
        
        while self.running:
            await asyncio.sleep(1)
            
    async def stop(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down...")
        self.running = False


# Global controller instance
controller = EdgeController()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    await controller.start()
    yield
    # Shutdown
    await controller.stop()


# FastAPI app for health checks and debugging
app = FastAPI(
    title="Inventory Edge Controller",
    version="2.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "running": controller.running
    }


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Smart Lab Inventory - Edge Controller",
        "version": "2.0.0",
        "docs": "/docs"
    }


def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal")
    asyncio.create_task(controller.stop())
    sys.exit(0)


async def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start web server for health checks
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
    server = uvicorn.Server(config)
    
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
