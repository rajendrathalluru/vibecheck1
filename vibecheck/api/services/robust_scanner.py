import traceback
from datetime import datetime
import re
from urllib.parse import urlsplit

from sqlalchemy import func, select

from api.agents import AGENT_MAP
from api.agents.http_tools import http_request
from api.config import settings
from api.models.assessment import Assessment
from api.models.finding import Finding


DEPTH_DISCOVERY_LIMITS = {
    "quick": {"seed_paths": 15, "max_requests": 12, "max_discovered": 25},
    "standard": {"seed_paths": 35, "max_requests": 24, "max_discovered": 55},
    "deep": {"seed_paths": 60, "max_requests": 40, "max_discovered": 90},
}

ROBUST_COMMON_PATHS = [
    "/",
    "/api",
    "/api/v1",
    "/api/v2",
    "/admin",
    "/dashboard",
    "/login",
    "/register",
    "/signup",
    "/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/swagger",
    "/graphql",
    "/graphiql",
    "/health",
    "/status",
    "/metrics",
    "/info",
    "/config",
    "/robots.txt",
    "/sitemap.xml",
    "/.well-known/security.txt",
    "/debug",
    "/actuator",
    "/api/users",
    "/api/auth",
    "/api/admin",
    "/api/profile",
    "/api/me",
    "/api/search?q=test",
    "/search?q=test",
]

_PATH_PATTERN = re.compile(r"""['"`](\/[A-Za-z0-9._~:/?#\[\]@!$&()*+,;=%-]{1,240})['"`]""")
_FETCH_PATTERN = re.compile(r"""(?:fetch|axios\.(?:get|post|put|patch|delete))\(\s*['"`](\/[^'"`]{1,240})['"`]""")


def _normalize_path(raw: str) -> str | None:
    if not raw or not raw.startswith("/"):
        return None
    parsed = urlsplit(raw)
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return path


def _extract_paths_from_body(body_preview: str) -> list[str]:
    if not body_preview:
        return []

    candidates = set()
    trimmed = body_preview[:12000]

    for match in _PATH_PATTERN.findall(trimmed):
        norm = _normalize_path(match)
        if norm:
            candidates.add(norm)

    for match in _FETCH_PATTERN.findall(trimmed):
        norm = _normalize_path(match)
        if norm:
            candidates.add(norm)

    # Skip obvious static asset extensions to focus request budget on app routes.
    excluded_suffixes = (
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
        ".woff", ".woff2", ".ttf", ".eot", ".map",
    )
    return sorted(p for p in candidates if not p.lower().endswith(excluded_suffixes))


async def _build_coverage_context(target_url: str, depth: str) -> dict:
    limits = DEPTH_DISCOVERY_LIMITS.get(depth, DEPTH_DISCOVERY_LIMITS["standard"])
    initial_queue = ROBUST_COMMON_PATHS[: limits["seed_paths"]]

    seen_paths: set[str] = set()
    queue: list[str] = []
    reachable_paths: list[dict] = []
    discovered_request_samples: list[str] = []

    def enqueue(path: str):
        if path in seen_paths:
            return
        if len(seen_paths) >= limits["max_discovered"]:
            return
        seen_paths.add(path)
        queue.append(path)

    for p in initial_queue:
        normalized = _normalize_path(p)
        if normalized:
            enqueue(normalized)

    probed = 0
    while queue and probed < limits["max_requests"]:
        path = queue.pop(0)
        result = await http_request(target_url, "GET", path)
        probed += 1

        if "error" in result:
            continue

        status = result.get("status_code")
        body = result.get("body_preview", "")
        if status is not None and status != 404:
            reachable_paths.append({"path": path, "status": status})

        for candidate in _extract_paths_from_body(body):
            enqueue(candidate)

        # Capture simple hints for agents (query/body candidates)
        if "?" in path and len(discovered_request_samples) < 10:
            discovered_request_samples.append(path)

    coverage_paths = sorted(seen_paths)
    return {
        "probed_count": probed,
        "seed_paths": coverage_paths,
        "reachable_paths": reachable_paths[:80],
        "request_samples": discovered_request_samples,
    }


async def run_robust_scan(
    assessment_id: str,
    target_url: str,
    agent_names: list[str],
    depth: str,
    db_factory,
):
    """
    Main robust scan orchestrator. Runs as a FastAPI BackgroundTask.
    Creates its own DB session since background tasks outlive the request.
    """
    async with db_factory() as db:
        assessment = await db.get(Assessment, assessment_id)
        if not assessment:
            return

        try:
            if not settings.GEMINI_API_KEY:
                assessment.status = "failed"
                assessment.error_type = "GEMINI_API_KEY_MISSING"
                assessment.error_message = (
                    "GEMINI_API_KEY is not configured. Robust mode requires Gemini credentials."
                )
                await db.commit()
                return

            assessment.status = "scanning"
            await db.commit()

            health_check = await http_request(target_url, "GET", "/")
            if "error" in health_check:
                assessment.status = "failed"
                assessment.error_type = "TARGET_UNREACHABLE"
                assessment.error_message = (
                    f"Cannot reach {target_url}: {health_check.get('message', health_check.get('error', 'request failed'))}"
                )[:500]
                await db.commit()
                return

            coverage_context = await _build_coverage_context(target_url, depth)

            succeeded_agents = 0
            failed_agents: list[str] = []

            for agent_name in agent_names:
                agent_class = AGENT_MAP.get(agent_name)
                if not agent_class:
                    continue

                try:
                    agent = agent_class(
                        assessment_id=assessment_id,
                        target_url=target_url,
                        depth=depth,
                        db_session=db,
                        coverage_context=coverage_context,
                    )
                    await agent.run()
                    succeeded_agents += 1
                    await db.commit()
                except Exception as e:
                    print(f"[robust_scanner] Agent '{agent_name}' failed: {e}")
                    traceback.print_exc()
                    failed_agents.append(f"{agent_name}: {str(e)[:180]}")
                    await db.rollback()
                    continue

            if succeeded_agents == 0:
                assessment.status = "failed"
                assessment.error_type = "AGENT_EXECUTION_FAILED"
                details = "; ".join(failed_agents) if failed_agents else "no agents ran"
                assessment.error_message = (
                    f"All robust agents failed. Check GEMINI_MODEL/GEMINI_API_KEY and logs. Details: {details}"
                )[:500]
                await db.commit()
                return

            count_query = (
                select(Finding.severity, func.count(Finding.id))
                .where(Finding.assessment_id == assessment_id)
                .group_by(Finding.severity)
            )
            result = await db.execute(count_query)
            severity_counts = dict(result.all())

            finding_counts = {
                "critical": severity_counts.get("critical", 0),
                "high": severity_counts.get("high", 0),
                "medium": severity_counts.get("medium", 0),
                "low": severity_counts.get("low", 0),
                "info": severity_counts.get("info", 0),
            }
            finding_counts["total"] = sum(finding_counts.values())

            assessment.finding_counts = finding_counts
            assessment.status = "complete"
            assessment.completed_at = datetime.utcnow()
            await db.commit()

        except Exception as e:
            assessment.status = "failed"
            assessment.error_type = "SCAN_ERROR"
            assessment.error_message = str(e)[:500]
            await db.commit()
