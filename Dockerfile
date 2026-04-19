# syntax=docker/dockerfile:1
FROM python:3.12-alpine AS base

# Install build deps needed for some wheels, then clean up
RUN apk add --no-cache gcc musl-dev libffi-dev

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Remove build tools to keep image lean
RUN apk del gcc musl-dev libffi-dev

COPY . .

RUN mkdir -p /app/data/logs

# Run as non-root for security
RUN adduser -D botuser && chown -R botuser /app
USER botuser

CMD ["python", "-m", "bot.main"]
