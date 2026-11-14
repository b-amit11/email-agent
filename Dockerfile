# The backend: the Python program that checks Gmail, drafts replies, and
# answers the dashboard.

FROM python:3.12-slim

# Show log lines straight away and do not write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install the packages first. This layer is reused until requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy the program and the fact sheets.
COPY app ./app
COPY knowledge ./knowledge

# Run as an ordinary user, not as the all-powerful root user.
RUN useradd --create-home appuser && mkdir -p /app/credentials && chown -R appuser /app
USER appuser

EXPOSE 8000

# One worker only: the background mail check must run exactly once.
# --proxy-headers lets the backend see the visitor's real address through the dashboard's web server.
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
