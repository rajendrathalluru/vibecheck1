import httpx


async def http_request(
    target_url: str,
    method: str,
    path: str,
    headers: dict | None = None,
    body: str | None = None,
    timeout: float = 10.0,
) -> dict:
    """
    Make an HTTP request to target_url + path.
    Returns status_code, headers, body_preview (truncated).
    On error returns an error dict instead of raising.
    """
    url = f"{target_url.rstrip('/')}{path}"
    try:
        async with httpx.AsyncClient(
            verify=False, follow_redirects=True, timeout=timeout
        ) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body_preview": response.text[:2000],
                "url": url,
            }
    except httpx.TimeoutException:
        return {"error": "timeout", "url": url, "message": f"Timed out after {timeout}s"}
    except httpx.ConnectError:
        return {"error": "connection_failed", "url": url, "message": f"Could not connect to {url}"}
    except Exception as e:
        return {"error": "request_failed", "url": url, "message": str(e)}


async def check_security_headers(target_url: str, path: str = "/") -> dict:
    """
    HEAD request to analyze security headers.
    Returns headers present, missing, and issues found.
    """
    result = await http_request(target_url, "HEAD", path)
    if "error" in result:
        return result

    headers = result.get("headers", {})
    headers_lower = {k.lower(): v for k, v in headers.items()}

    expected = [
        "x-content-type-options",
        "x-frame-options",
        "strict-transport-security",
        "content-security-policy",
        "referrer-policy",
        "permissions-policy",
    ]
    missing = [h for h in expected if h not in headers_lower]

    issues: list[str] = []

    cors = headers_lower.get("access-control-allow-origin")
    if cors == "*":
        issues.append("CORS allows all origins (wildcard *)")

    x_powered = headers_lower.get("x-powered-by")
    if x_powered:
        issues.append(f"X-Powered-By exposes technology: {x_powered}")

    server = headers_lower.get("server")
    if server and any(
        v in server.lower()
        for v in ["apache", "nginx", "express", "flask", "werkzeug", "gunicorn", "php"]
    ):
        issues.append(f"Server header discloses software: {server}")

    if missing:
        issues.append(f"Missing security headers: {', '.join(missing)}")

    return {
        "headers": headers,
        "missing_security_headers": missing,
        "issues": issues,
    }
