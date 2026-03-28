FROM python:3.12-slim AS base

LABEL maintainer="Erick Guerron"
LABEL description="Context-Life (CL) — LLM Context Optimization MCP Server"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md ./
COPY mmcp/ ./mmcp/

# Install with all dependencies
RUN pip install --no-cache-dir ".[rag]"

# Runtime user (non-root)
RUN useradd --create-home cluser
USER cluser

# Health check: verify CLI works
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD context-life version || exit 1

# Default: start stdio server
ENTRYPOINT ["context-life"]
CMD ["serve"]
