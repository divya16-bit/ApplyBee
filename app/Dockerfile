# Use Python 3.11 (NOT 3.13)
FROM python:3.11-slim

# Install minimal system dependencies required for:
# - certificates
# - building Python wheels
# - sentence-transformers / torch CPU ops
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    git \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies (use production requirements if exists, else regular)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt || pip install --no-cache-dir -r requirements_old.txt


# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]