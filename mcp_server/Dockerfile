FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    VIBECHECK_TIMEOUT_SECONDS=30 \
    MCP_TRANSPORT=streamable-http \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8787 \
    MCP_PATH=/mcp

WORKDIR /app

COPY vibecheck_mcp_server.py /app/vibecheck_mcp_server.py

RUN python -m pip install --upgrade pip \
    && python -m pip install mcp httpx

EXPOSE 8787

CMD ["python", "/app/vibecheck_mcp_server.py"]
