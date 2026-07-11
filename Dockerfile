FROM python:3.12-slim AS builder
WORKDIR /app

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip
RUN if [ -f requirements.txt ]; then pip wheel -r requirements.txt -w /wheels; fi

FROM python:3.12-slim
WORKDIR /app

# Create non-root user
RUN useradd -m appuser

# Install Tesseract OCR for camera CV scanning (all supported languages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-tur \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-spa \
    tesseract-ocr-ara \
    tesseract-ocr-por \
    tesseract-ocr-ita \
    tesseract-ocr-nld \
    tesseract-ocr-rus \
    tesseract-ocr-jpn \
    tesseract-ocr-kor \
    tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels if any and install
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt

# Copy source
COPY . /app
RUN sed -i 's/\r$//' /app/start_gunicorn.sh /app/gunicorn_config.py
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8001

# Healthcheck (checks /health endpoint)
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2).read()" || exit 1

ENV PYTHONUNBUFFERED=1
CMD ["/bin/bash", "./start_gunicorn.sh"]
