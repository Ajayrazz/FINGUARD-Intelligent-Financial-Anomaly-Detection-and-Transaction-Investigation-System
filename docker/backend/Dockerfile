FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# Tesseract OCR engine (invoice text extraction, Phase 8)
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY backend/requirements/ requirements/
ARG REQS=dev
RUN pip install --no-cache-dir -r requirements/${REQS}.txt -c requirements/constraints.txt
COPY backend/ .
EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
