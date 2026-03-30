FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

LABEL maintainer="Erick Guerron"
LABEL description="Context-Life (CL) — LLM Context Optimization MCP Server"

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY mmcp/ ./mmcp/

# Install runtime dependencies only (keep image lean)
RUN pip install --no-compile ".[rag]"

# Runtime user (non-root)
RUN useradd --create-home --shell /usr/sbin/nologin cluser
USER cluser

# Health check: verify CLI works
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD context-life version || exit 1

# Default: start stdio server
ENTRYPOINT ["context-life"]
CMD ["serve"]
