# VibeCheck MCP Server

This folder provides an MCP server for the VibeCheck API.

## Why this shape
- Transport: `stdio` (most reliable in Cursor)
- Implementation: Python FastMCP
- Scope: thin tool wrapper over your `/v1/*` API

## Prerequisites
1. VibeCheck API running (local or hosted)
2. Python environment with:
   - `mcp`
   - `httpx`

Install (local):

```bash
cd /Users/rajendrathalluru/Documents/vibeccheck/VibeCheck
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install mcp httpx
```

## Run manually (stdio)

```bash
cd /Users/rajendrathalluru/Documents/vibeccheck/VibeCheck
source .venv/bin/activate
VIBECHECK_API_BASE=https://vibecheck1-257d3ab2.aedify.ai \
python mcp_server/vibecheck_mcp_server.py
```

## Run manually (streamable-http, local-only)

```bash
cd /Users/rajendrathalluru/Documents/vibeccheck/VibeCheck
source .venv/bin/activate
VIBECHECK_API_BASE=https://vibecheck1-257d3ab2.aedify.ai \
python mcp_server/vibecheck_mcp_server.py \
  --transport streamable-http \
  --host 127.0.0.1 \
  --port 8787 \
  --path /mcp
```

## Run manually (streamable-http, public)

Use this when clients are on a different machine/network:

```bash
cd /Users/rajendrathalluru/Documents/vibeccheck/VibeCheck
source .venv/bin/activate
VIBECHECK_API_BASE=https://vibecheck1-257d3ab2.aedify.ai \
python mcp_server/vibecheck_mcp_server.py \
  --transport streamable-http \
  --host 0.0.0.0 \
  --port 8787 \
  --path /mcp
```

Then expose this service behind HTTPS and share:

```text
https://<your-mcp-domain>/mcp
```

## Deploy MCP as a container

Build:

```bash
cd /Users/rajendrathalluru/Documents/vibeccheck/VibeCheck
docker build -f mcp_server/Dockerfile -t vibecheck-mcp .
```

Run:

```bash
docker run --rm -p 8000:8000 \
  -e VIBECHECK_API_BASE=https://vibecheck1-257d3ab2.aedify.ai \
  vibecheck-mcp
```

## AEDIFY deployment (recommended)

If deploying as a monorepo component:

- Base Directory: `mcp_server`
- Dockerfile: `Dockerfile`
- Environment:
  - `PORT=8000`
  - `MCP_HOST=0.0.0.0`
  - `MCP_TRANSPORT=streamable-http`
  - `MCP_PATH=/mcp`
  - `VIBECHECK_API_BASE=https://vibecheck1-257d3ab2.aedify.ai`

The server binds to `PORT` for HTTP transports, which avoids 502 errors on platforms
that require a specific internal port.

## Troubleshooting

- `502 Bad Gateway`:
  - Usually a bind-port mismatch. Ensure `PORT=8000` and redeploy.
- `Invalid session ID` loops:
  - Ensure one MCP replica (no multi-instance LB while testing).
  - Ensure proxy/CDN preserves `mcp-session-id` request/response headers.
  - Disable caching for `/mcp`.

## Cursor MCP config

Add to your Cursor MCP config (`mcp.json`):

```json
{
  "mcpServers": {
    "vibecheck": {
      "command": "/Users/rajendrathalluru/Documents/vibeccheck/VibeCheck/.venv/bin/python",
      "args": [
        "/Users/rajendrathalluru/Documents/vibeccheck/VibeCheck/mcp_server/vibecheck_mcp_server.py"
      ],
      "env": {
        "VIBECHECK_API_BASE": "https://vibecheck1-257d3ab2.aedify.ai",
        "VIBECHECK_TIMEOUT_SECONDS": "30"
      }
    }
  }
}
```

If your backend is hosted, set `VIBECHECK_API_BASE` to your deployed API URL.

## Cursor config (streamable-http)

If you run this MCP server as HTTP, Cursor can connect by URL:

```json
{
  "mcpServers": {
    "vibecheck-http": {
      "url": "http://127.0.0.1:8787/mcp"
    }
  }
}
```

For a remote deployment, replace with your public endpoint URL.

## Remote client config (streamable-http)

Any MCP client that supports URL-based streamable-http can use:

```json
{
  "mcpServers": {
    "vibecheck-remote": {
      "url": "https://<your-mcp-domain>/mcp"
    }
  }
}
```

## Security note

This MCP server currently has no built-in authentication.
Do not expose it publicly without network controls or auth at your reverse proxy.

## Exposed tools
- `health`
- `list_agents`
- `create_assessment`
- `list_assessments`
- `get_assessment`
- `rerun_assessment`
- `list_findings`
- `analyze_finding`
- `list_tunnel_sessions`
- `memory_search`
