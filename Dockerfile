# syntax=docker/dockerfile:1

# ---- frontend: build the React app ---------------------------------------------------------
# VITE_* values are baked into the bundle at build time (pass them with --build-arg).
FROM node:24-slim AS frontend
WORKDIR /frontend
ARG VITE_SUPABASE_URL
ARG VITE_SUPABASE_ANON_KEY
ENV VITE_SUPABASE_URL=$VITE_SUPABASE_URL VITE_SUPABASE_ANON_KEY=$VITE_SUPABASE_ANON_KEY VITE_HTTPS=false
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

# ---- app: API + built frontend in one container (runs migrations, then serves) -------------
FROM python:3.14-slim AS app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 POETRY_VIRTUALENVS_CREATE=false
WORKDIR /app
RUN pip install "poetry==2.2.1"

# Dependencies first, so this layer is cached until pyproject/poetry.lock change
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --only main --no-root

COPY settings.toml alembic.ini ./
COPY assets ./assets
COPY migrations ./migrations
COPY crm ./crm
RUN poetry install --only main
COPY --from=frontend /frontend/dist ./frontend/dist
ENV API_STATIC_DIR=/app/frontend/dist

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn --factory crm.api.app:create_app --host 0.0.0.0 --port 8000"]

# ---- tests: same image plus dev dependencies and the test suite ---------------------------
FROM app AS tests
RUN poetry install
COPY tests ./tests
HEALTHCHECK NONE
CMD ["pytest", "-q"]
