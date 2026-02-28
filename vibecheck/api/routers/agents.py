from fastapi import APIRouter

from api.utils.errors import VibeCheckError

router = APIRouter(tags=["Agents"])

AGENTS = [
    {
        "name": "recon",
        "display_name": "Reconnaissance Agent",
        "description": "Maps routes, discovers hidden endpoints, admin panels, debug pages, directory listings, exposed files.",
        "categories": [
            "exposed_endpoints",
            "directory_listing",
            "debug_mode",
            "information_disclosure",
        ],
        "mode": "robust",
    },
    {
        "name": "auth",
        "display_name": "Authentication Agent",
        "description": "Tests for missing auth, default credentials, broken access control (IDOR), session issues, privilege escalation.",
        "categories": [
            "missing_auth",
            "broken_access_control",
            "idor",
            "session_manipulation",
        ],
        "mode": "robust",
    },
    {
        "name": "injection",
        "display_name": "Injection Agent",
        "description": "Probes for SQL injection, XSS, command injection, template injection with real payloads.",
        "categories": [
            "sql_injection",
            "xss",
            "command_injection",
            "template_injection",
        ],
        "mode": "robust",
    },
    {
        "name": "config",
        "display_name": "Configuration Agent",
        "description": "Checks security headers, CORS, exposed stack traces, debug mode, server info disclosure.",
        "categories": [
            "cors_misconfiguration",
            "missing_headers",
            "exposed_stacktrace",
            "insecure_tls",
        ],
        "mode": "robust",
    },
    {
        "name": "static",
        "display_name": "Static Analyzer",
        "description": "Analyzes source code for hardcoded secrets, vulnerable dependencies, insecure patterns, dangerous defaults.",
        "categories": [
            "hardcoded_secret",
            "vulnerable_dependency",
            "insecure_pattern",
            "dangerous_default",
        ],
        "mode": "lightweight",
    },
]


@router.get("/v1/agents")
async def list_agents():
    return {"data": AGENTS}


@router.get("/v1/agents/{agent_name}")
async def get_agent(agent_name: str):
    for a in AGENTS:
        if a["name"] == agent_name:
            return a
    raise VibeCheckError.not_found("Agent", agent_name)
