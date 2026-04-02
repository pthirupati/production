FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (including Docker CLI for container management + pg client for wait_for_db)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    gnupg \
    postgresql-client \
    && curl -fsSL https://get.docker.com | sh \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Project code
COPY . .

# Create directories for static/media
RUN mkdir -p staticfiles media

EXPOSE 8000

# Use startup script which runs migrations + collectstatic + daphne
CMD ["/bin/sh", "/scripts/startup.sh"]

