# Edge Controller for Raspberry Pi
# Python-based hardware controller for Smart Inventory System

FROM python:3.11-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libgpiod2 \
    python3-libgpiod \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create data directory for SQLite cache
RUN mkdir -p /app/data

# Expose health check port
EXPOSE 8080

# Run the controller
CMD ["python", "-m", "src.main"]
