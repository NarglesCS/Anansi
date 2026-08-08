# Build stage: compile React app
FROM node:22-slim as build

WORKDIR /app/ui

# Copy package files
COPY ui/package*.json ./

# Install dependencies
RUN npm ci

# Copy source
COPY ui/src ./src
COPY ui/public ./public
COPY ui/index.html \
     ui/vite.config.ts \
     ui/tsconfig.json \
     ui/tsconfig.node.json \
     ./

# Build React app
RUN npm run build

# Runtime stage: Python Flask proxy + built assets
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ANANSI_ALLOW_MUTATIONS=0 \
    ANANSI_MAX_DEPTH=10 \
    ANANSI_MAX_COMPLEXITY=100 \
    ANANSI_MAX_RESULT_BYTES=262144

WORKDIR /app

# Copy the entire repo (to access anansi package)
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir flask flask-cors

# Copy built React app from build stage
COPY --from=build /app/ui/dist /app/ui/dist

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/graphql')" || exit 1

EXPOSE 8000

# Run the Flask proxy (which serves the built UI + GraphQL endpoint)
CMD ["python", "/app/ui/proxy.py"]
