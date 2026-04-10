# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# ── Stage 2: Python runtime ───────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required to compile lxml
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python source and data files
COPY *.py ./
COPY *.json ./

# Copy built React frontend from Stage 1
COPY --from=frontend /app/dist ./dist

# Railway injects PORT at runtime; default to 8000 for local Docker runs
ENV PORT=8000
EXPOSE 8000

CMD ["python", "04_api_server.py"]
