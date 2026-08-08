FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANANSI_ALLOW_MUTATIONS=0 \
    ANANSI_MAX_DEPTH=10 \
    ANANSI_MAX_COMPLEXITY=100 \
    ANANSI_MAX_RESULT_BYTES=262144

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

ENTRYPOINT ["python", "-m", "anansi.server"]
