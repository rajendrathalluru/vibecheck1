"""
VibeCheck MCP Server (stdio-first) for Cursor.

Environment variables:
- VIBECHECK_API_BASE (default: http://127.0.0.1:8000)
- VIBECHECK_TIMEOUT_SECONDS (default: 30)
"""

from __future__ import annotations

import argparse
import inspect
import os
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP


API_BASE = os.getenv("VIBECHECK_API_BASE", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT_SECONDS = float(os.getenv("VIBECHECK_TIMEOUT_SECONDS", "30"))
DEFAULT_PORT = int(os.getenv("PORT", "8000"))

mcp = FastMCP("VibeCheck MCP")


async def _api_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        resp = await client.request(
            method=method.upper(),
            url=url,
            params=params,
            json=json_body,
            headers={"Content-Type": "application/json"},
        )
    try:
        payload = resp.json() if resp.content else {}
    except Exception:
        payload = {"raw": resp.text}

    if resp.status_code >= 400:
        return {
            "ok": False,
            "status_code": resp.status_code,
            "error": payload.get("error", payload),
            "url": url,
        }

    return {
        "ok": True,
        "status_code": resp.status_code,
        "data": payload,
        "url": url,
    }


@mcp.tool()
async def health() -> dict[str, Any]:
    """Check VibeCheck API health."""
    return await _api_request("GET", "/v1/health")


@mcp.tool()
async def list_agents() -> dict[str, Any]:
    """List available scan agents."""
    return await _api_request("GET", "/v1/agents")


@mcp.tool()
async def create_assessment(
    mode: Literal["lightweight", "robust"],
    repo_url: str | None = None,
    target_url: str | None = None,
    tunnel_session_id: str | None = None,
    depth: Literal["quick", "standard", "deep"] = "standard",
    agents: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """
    Create a VibeCheck assessment.
    - lightweight: provide repo_url
    - robust: provide target_url (optional tunnel_session_id)
    """
    body: dict[str, Any] = {"mode": mode}
    if repo_url:
        body["repo_url"] = repo_url
    if target_url:
        body["target_url"] = target_url
    if tunnel_session_id:
        body["tunnel_session_id"] = tunnel_session_id
    if agents:
        body["agents"] = agents
    if depth:
        body["depth"] = depth
    if idempotency_key:
        body["idempotency_key"] = idempotency_key

    return await _api_request("POST", "/v1/assessments", json_body=body)


@mcp.tool()
async def list_assessments(
    page: int = 1,
    per_page: int = 20,
    mode: str | None = None,
    status: str | None = None,
    sort: str = "-created_at",
) -> dict[str, Any]:
    """List assessments with pagination/filtering."""
    params: dict[str, Any] = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
    }
    if mode:
        params["mode"] = mode
    if status:
        params["status"] = status
    return await _api_request("GET", "/v1/assessments", params=params)


@mcp.tool()
async def get_assessment(assessment_id: str) -> dict[str, Any]:
    """Get one assessment by id."""
    return await _api_request("GET", f"/v1/assessments/{assessment_id}")


@mcp.tool()
async def rerun_assessment(
    assessment_id: str,
    agents: list[str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Re-run a completed/failed assessment."""
    body: dict[str, Any] = {}
    if agents is not None:
        body["agents"] = agents
    if idempotency_key is not None:
        body["idempotency_key"] = idempotency_key
    return await _api_request(
        "POST",
        f"/v1/assessments/{assessment_id}/rerun",
        json_body=body,
    )


@mcp.tool()
async def list_findings(
    assessment_id: str,
    page: int = 1,
    per_page: int = 20,
    severity: str | None = None,
    category: str | None = None,
    agent: str | None = None,
    sort: str = "severity",
) -> dict[str, Any]:
    """List findings for an assessment."""
    params: dict[str, Any] = {
        "page": page,
        "per_page": per_page,
        "sort": sort,
    }
    if severity:
        params["severity"] = severity
    if category:
        params["category"] = category
    if agent:
        params["agent"] = agent
    return await _api_request(
        "GET",
        f"/v1/assessments/{assessment_id}/findings",
        params=params,
    )


@mcp.tool()
async def analyze_finding(
    assessment_id: str,
    finding_id: str,
    focus: str | None = None,
) -> dict[str, Any]:
    """Run AI analysis for one finding, with optional focus guidance."""
    body: dict[str, Any] = {}
    if focus:
        body["focus"] = focus
    return await _api_request(
        "POST",
        f"/v1/assessments/{assessment_id}/findings/{finding_id}/analyze",
        json_body=body,
    )


@mcp.tool()
async def list_tunnel_sessions() -> dict[str, Any]:
    """List tunnel sessions."""
    return await _api_request("GET", "/v1/tunnel/sessions")


@mcp.tool()
async def memory_search(
    q: str,
    limit: int = 5,
    assessment_id: str | None = None,
) -> dict[str, Any]:
    """Search similar historical findings from VibeCheck memory."""
    params: dict[str, Any] = {"q": q, "limit": limit}
    if assessment_id:
        params["assessment_id"] = assessment_id
    return await _api_request("GET", "/v1/memory/search", params=params)


def main() -> None:
    parser = argparse.ArgumentParser(description="VibeCheck MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP transport to run",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Host for HTTP/SSE transports",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", str(DEFAULT_PORT))),
        help="Port for HTTP/SSE transports",
    )
    parser.add_argument(
        "--path",
        default=os.getenv("MCP_PATH", "/mcp"),
        help="Path for Streamable HTTP transport",
    )
    args = parser.parse_args()

    # Support multiple MCP SDK versions by passing only supported kwargs.
    run_sig = inspect.signature(mcp.run)
    kwargs: dict[str, Any] = {}
    if "transport" in run_sig.parameters:
        kwargs["transport"] = args.transport
    if args.transport != "stdio":
        if "host" in run_sig.parameters:
            kwargs["host"] = args.host
        if "port" in run_sig.parameters:
            kwargs["port"] = args.port
        if "path" in run_sig.parameters and args.transport == "streamable-http":
            kwargs["path"] = args.path

    mcp.run(**kwargs)


if __name__ == "__main__":
    main()
