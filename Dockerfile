# Multi-stage Dockerfile for Access Control Middleware
# Supports both app server and migration modes
#
# Build:
#   docker build -t access-control-middleware:latest .
#
# Run (app server):
#   docker run -p 8000:8000 access-control-middleware:latest
#
# Run (migrations):
#   docker run access-control-middleware:latest python -m app.cli migrate
#   docker run access-control-middleware:latest python -m app.cli status
#
# With docker-compose:
#   docker-compose up middleware
#   docker-compose run --profile tools migration

# Stage 1: Base Python runtime
FROM python:3.12-slim as base

LABEL maintainer="Access Control Team"
LABEL description="HikVision Access Control Middleware - Production Container"

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    sqlite3 \
    libsqlcipher-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Development build (with dev dependencies)
FROM base as dev

RUN pip install --no-cache-dir \
    pytest==7.4.3 \
    pytest-cov==4.1.0 \
    black==23.12.0 \
    flake8==6.1.0 \
    mypy==1.7.1

COPY . .
RUN chmod +x /app/scripts/*.sh

ENTRYPOINT ["python"]
CMD ["-m", "app.main"]

# Stage 3: Production build (lean and secure)
FROM base as production

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash acm-user

# Copy application code
COPY --chown=acm-user:acm-user app/ ./app/
COPY --chown=acm-user:acm-user migrations/ ./migrations/
COPY --chown=acm-user:acm-user scripts/ ./scripts/

# Create necessary directories
RUN mkdir -p logs data && \
    chown -R acm-user:acm-user logs data

# Switch to non-root user
USER acm-user

# Health check (for Docker and Kubernetes)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

# Default command (app server)
# Can be overridden by docker-compose for migrations
ENTRYPOINT ["/bin/bash", "-c"]
CMD ["python -m app.main"]

# Runtime labels for metadata
LABEL version="1.0.0" \
      commit="$BUILD_COMMIT" \
      timestamp="$BUILD_TIMESTAMP"

# Expose FastAPI port (for docker-compose integration)
EXPOSE 8000
