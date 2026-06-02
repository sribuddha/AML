# Stage 1 — Build frontend
FROM node:22-alpine AS frontend-builder
WORKDIR /app/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ .
RUN npm run build

# Stage 2 — Install Python dependencies
FROM python:3.14-slim AS python-deps
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY common/ common/
RUN pip install uv && uv sync --no-dev --no-editable

# Stage 3 — Runtime image
FROM python:3.14-slim
WORKDIR /app
COPY --from=python-deps /app/.venv /app/.venv
COPY --from=frontend-builder /app/ui/dist /app/ui/dist
COPY src/ src/
COPY scripts/ scripts/
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
CMD ["uvicorn", "src.bff.app:app", "--host", "0.0.0.0", "--port", "8000"]
