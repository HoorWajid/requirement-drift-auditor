# ---- Stage 1: build dependencies ----
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements-docker.txt .
RUN pip install --no-cache-dir --user -r requirements-docker.txt

# ---- Stage 2: runtime ----
FROM python:3.11-slim
WORKDIR /app

# Install libmagic (needed by python-magic) — minimal, no build toolchain in final image
RUN apt-get update && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — running as root in a container is an unnecessary privilege-escalation surface
RUN useradd --create-home appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY . .
RUN chown -R appuser:appuser /app
USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1

EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import requests; requests.get('http://localhost:7860/health').raise_for_status()"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
