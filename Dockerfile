# syntax=docker/dockerfile:1

# ---- Builder: install build deps and dependencies into an isolated venv ----
FROM python:3.12-alpine AS builder

RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---- Runtime: only the virtualenv + app code, no build tools ----
FROM python:3.12-alpine

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY . .

RUN mkdir -p /app/data/logs

# Keep root runtime here because a mounted Docker volume at /app/data
# may be owned by root and break log/database writes for non-root users.

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import bot.core.healthcheck" || exit 1

CMD ["python", "-m", "bot.main"]
