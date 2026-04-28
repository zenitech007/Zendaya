# Stage 1: Build frontend
FROM node:18-alpine AS frontend-build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html vite.config.ts tsconfig.json tsconfig.app.json tsconfig.node.json ./
COPY tailwind.config.js postcss.config.js eslint.config.js ./
COPY src/ src/
RUN npm run build

# Stage 2: Backend
FROM python:3.11-slim AS backend
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY zendaya_backend/ zendaya_backend/
COPY alembic/ alembic/
COPY alembic.ini .
COPY pyproject.toml .

COPY --from=frontend-build /app/dist /app/static

EXPOSE 8000

CMD ["uvicorn", "zendaya_backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
