# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Dockerfile for Code Knowledge Chain (CKC)
#
# Multi-stage build:
#   Stage 1 (builder)  – install Python + Node deps, engine binaries
#   Stage 2 (runtime)  – slim image with just what's needed to serve
#
# Build:   docker build -t ckc .
# Run:     docker run -p 8000:8000 -v /path/to/repo:/project ckc
# ---------------------------------------------------------------------------

# ---- Stage 1: Builder ----
FROM python:3.12-slim AS builder

# Install Node.js (LTS) for gitnexus + codegraph engines
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Install engine CLIs globally (pinned — bump with pyproject [tool.code-knowledge-chain.engines])
RUN pip install --no-cache-dir "graphifyy==0.9.56" && \
    npm install -g gitnexus@1.6.11 @colbymchenry/codegraph@1.6.0

# ---- Stage 2: Runtime ----
FROM python:3.12-slim AS runtime

# Install Node.js runtime + git (needed by gitnexus for git log analysis)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git ca-certificates && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages + CLI entry points
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy installed Node.js global packages
COPY --from=builder /usr/lib/node_modules /usr/lib/node_modules
COPY --from=builder /usr/bin/gitnexus /usr/bin/gitnexus
COPY --from=builder /usr/bin/codegraph /usr/bin/codegraph

# Copy application source
WORKDIR /app
COPY src/ src/
COPY pyproject.toml README.md ./
COPY examples/ examples/

# Create non-root user
RUN useradd --create-home --shell /bin/bash ckc && \
    chown -R ckc:ckc /app
USER ckc

# Environment defaults
ENV CKC_HOST=0.0.0.0 \
    CKC_PORT=8000 \
    CKC_LOG_FORMAT=json \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

ENTRYPOINT ["python", "-m", "uvicorn", "code_chain.ui.server:app"]
CMD ["--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
