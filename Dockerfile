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

# Install Python dependencies in separate layers to reduce memory pressure
# Using pydantic v1 (pure Python) to avoid pydantic-core Rust compilation
RUN pip install --no-cache-dir python-dotenv requests
RUN pip install --no-cache-dir pydantic==1.10.21
RUN pip install --no-cache-dir fastapi==0.99.1 uvicorn
RUN pip install --no-cache-dir openai==1.10.0

# Copy Python source and data files
COPY *.py ./
COPY *.json ./

# Copy built React frontend from Stage 1
COPY --from=frontend /app/dist ./dist

# Railway injects PORT at runtime; default to 8000 for local Docker runs
ENV PORT=8000
EXPOSE 8000

CMD ["python", "04_api_server.py"]
