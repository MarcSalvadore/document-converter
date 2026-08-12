# Multi-stage production-ready Dockerfile for Document-to-Markdown Converter API

# -----------------------------------------------------------------------------
# Stage 1: Build Dependencies
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install minimal OS dependencies for wheel compilation if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements into build wheel directory
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Final Lightweight Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runner

# Set environment variables for Python performance and non-buffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install minimal runtime font / layout OS packages and cleanup layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    fontconfig \
    libfreetype6 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Create non-root user and group for security
RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/sh -m appuser

# Copy application source code into container
COPY . /app/converter_engine

# Change ownership of /app to non-root appuser
RUN chown -R appuser:appgroup /app

# Switch to non-root user execution context
USER appuser:appgroup

# Expose API application port
EXPOSE 8000

# Health check instruction for container orchestration
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

# Execute ASGI server via uvicorn
CMD ["uvicorn", "converter_engine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
