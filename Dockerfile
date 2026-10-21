# --- Stage 1: Builder ---
FROM python:3.11-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# --- Stage 2: Final (Minimal & Sicher) ---
FROM python:3.11-slim AS final

WORKDIR /app

# Kopiere die installierten Python-Pakete aus der Builder-Stage
COPY --from=builder /root/.local /home/appuser/.local
COPY main.py .

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# CALOSPRO-54: Sicherheits-Best-Practice – Non-Root User
RUN useradd -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
