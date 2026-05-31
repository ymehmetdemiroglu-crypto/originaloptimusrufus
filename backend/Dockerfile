FROM python:3.11-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim as runner

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy python dependencies
COPY --from=builder /root/.local /home/appuser/.local
RUN chown -R appuser:appuser /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copy backend, acquisition tool workspace (needed for shared prompts/tools), and data directories
COPY --chown=appuser:appuser backend/ ./backend
COPY --chown=appuser:appuser acquisition-tool/ ./acquisition-tool

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="/app/backend:/app/acquisition-tool"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')"

USER appuser

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
