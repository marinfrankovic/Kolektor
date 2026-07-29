# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim AS runtime

ARG WITH_REMBG=false

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# libglib2.0-0 is required by opencv-python-headless.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt backend/requirements-ml.txt ./
RUN pip install -r requirements.txt \
    && if [ "$WITH_REMBG" = "true" ]; then pip install -r requirements-ml.txt; fi

COPY backend/app ./app
COPY --from=frontend /build/dist ./static

RUN useradd --system --create-home --uid 10001 kolektor \
    && mkdir -p /data/media \
    && chown -R kolektor:kolektor /data /app

USER kolektor

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
