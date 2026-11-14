# One image holding the whole project: the dashboard page and the Python backend.

# Stage 1: build the dashboard into plain web files.
FROM node:22-alpine AS dashboard
WORKDIR /build
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ .
RUN npm run build

# Stage 2: the Python program, which also serves those web files.
FROM python:3.12-slim

# Show log lines straight away and do not write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install the packages first. This layer is reused until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the program, the fact sheets, and the built dashboard.
COPY app ./app
COPY knowledge ./knowledge
COPY --from=dashboard /build/dist ./dashboard/dist

# Run as an ordinary user, not as the all-powerful root user.
RUN useradd --create-home appuser && mkdir -p /app/credentials && chown -R appuser /app
USER appuser

EXPOSE 8000

# One worker only: the background mail check must run exactly once.
# Hosting services say which port to listen on through PORT; 8000 is the fallback.
# --proxy-headers lets the program see the visitor's real address behind the host's web server.
CMD ["sh", "-c", "exec python -m uvicorn app.site:site --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
