# Stage 1: build the frontend
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: FastAPI serves the API and the built frontend from one service
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 CREWAI_DISABLE_TELEMETRY=true OTEL_SDK_DISABLED=true
WORKDIR /app/backend
# libgl / glib: needed by OpenCV, which the OCR model uses
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 \
    && (apt-get install -y --no-install-recommends libglib2.0-0 || apt-get install -y --no-install-recommends libglib2.0-0t64) \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt ./
RUN pip install -r requirements.txt
# Pretrained model weights are fetched once at build time (never at request time). This layer is cached
# until the registry or the fetch script changes. A failed download leaves that slot MODEL_UNAVAILABLE.
COPY backend/app/__init__.py ./app/__init__.py
COPY backend/app/ml/ ./app/ml/
COPY backend/scripts/fetch_models.py ./scripts/fetch_models.py
RUN python scripts/fetch_models.py
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
