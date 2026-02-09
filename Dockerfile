# =============================================================================
# Admin System Core - Dockerfile
# =============================================================================
# Multi-stage build for optimized production image

# -----------------------------------------------------------------------------
# Stage 1: Builder
# -----------------------------------------------------------------------------
FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
# 安裝 CPU 版 PyTorch (大幅減少體積與下載時間)
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime
# -----------------------------------------------------------------------------
FROM python:3.12-slim as runtime

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

# Copy Python packages from builder to appuser home
COPY --from=builder /root/.local /home/appuser/.local

# Ensure permissions
RUN chown -R appuser:appuser /home/appuser/.local

# Make sure scripts in .local are usable
ENV PATH=/home/appuser/.local/bin:$PATH

# Set working directory to src/admin_system for imports
WORKDIR /app

# Copy application source code (src layout)
COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser tests/ /app/tests/
COPY --chown=appuser:appuser scripts/ /app/scripts/
COPY --chown=appuser:appuser static/ /app/static/
COPY --chown=appuser:appuser docs/ /app/docs/
COPY --chown=appuser:appuser resources/ /app/resources/
COPY --chown=appuser:appuser ragic_registry.json /app/
COPY --chown=appuser:appuser pyproject.toml /app/

# Set PYTHONPATH to include src/admin_system for bare imports (core., api., modules., utils.)
ENV PYTHONPATH=/app/src/admin_system:$PYTHONPATH

USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/')" || exit 1

# Run the application from src/admin_system
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
