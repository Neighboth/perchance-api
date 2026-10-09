FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install system dependencies needed for Playwright and Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ca-certificates \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY perchance/ ./perchance/
COPY examples/ ./examples/

# Install Python package and dependencies
RUN pip install --no-cache-dir -e . && \
    pip install --no-cache-dir uvicorn fastapi python-dotenv pydantic requests playwright && \
    playwright install --with-deps chromium

# Expose server port
EXPOSE 8000

# Run OpenAI-compatible API server
CMD ["python", "examples/server.py"]
