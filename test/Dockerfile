# --------------------------------------------------
# FixitLab E2E Smoke Test Container
# --------------------------------------------------
FROM python:3.12-slim

# Install system deps for Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libxkbcommon0 \
    libgtk-3-0 \
    libasound2 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxshmfence1 \
    libdrm2 \
    libxcomposite1 \
    libxfixes3 \
    libxext6 \
    libxcb1 \
    libx11-6 \
    libx11-xcb1 \
    libxrender1 \
    ca-certificates \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /tests

# Copy smoke test
COPY smoketest_e2e.py .

# Install python deps
RUN pip install --no-cache-dir playwright \
    && playwright install chromium

# Default command
CMD ["python", "smoketest_e2e.py"]

