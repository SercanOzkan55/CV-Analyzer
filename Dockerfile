FROM python:3.11-slim AS builder
WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip wheel -r requirements.txt -w /wheels; fi

FROM python:3.11-slim
WORKDIR /app

# Create non-root user
RUN useradd -m appuser

# Copy wheels if any and install
COPY --from=builder /wheels /wheels
RUN if [ -d /wheels ]; then pip install --no-index --find-links=/wheels -r requirements.txt || true; fi

# Copy source
COPY . /app
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Healthcheck (checks root URL)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD wget -qO- http://localhost:8000/ || exit 1

ENV PYTHONUNBUFFERED=1
CMD ["/bin/bash", "./start_gunicorn.sh"]
