import json
from datetime import datetime

from google import genai
from google.genai import types

from api.agents.http_tools import check_security_headers, http_request
from api.config import settings
from api.models.agent_log import AgentLog
from api.models.finding import Finding
from api.services.supermemory_service import SupermemoryService
from api.utils.id_generator import generate_id

AGENT_TOOLS = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="http_request",
            description=(
                "Make an HTTP request to the target application. "
                "Use this to probe endpoints, submit forms, test payloads, and observe responses."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "method": types.Schema(
                        type="STRING",
                        enum=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                        description="HTTP method",
                    ),
                    "path": types.Schema(
                        type="STRING",
                        description="Path relative to target, e.g. /api/users or /admin",
                    ),
                    "headers": types.Schema(
                        type="OBJECT",
                        description="Optional request headers as key-value pairs",
                    ),
                    "body": types.Schema(
                        type="STRING",
                        description="Optional request body (for POST/PUT/PATCH)",
                    ),
                },
                required=["method", "path"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_headers",
            description=(
                "Check security headers on a specific path. Returns which security headers "
                "are present, missing, and any issues (CORS, server disclosure, etc.)."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "path": types.Schema(
                        type="STRING", description="Path to check, defaults to /"
                    ),
                },
            ),
        ),
        types.FunctionDeclaration(
            name="report_finding",
            description=(
                "Report a confirmed or highly likely security vulnerability. "
                "Only call this when you have evidence from probing, not for theoretical issues."
            ),
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "severity": types.Schema(
                        type="STRING",
                        enum=["critical", "high", "medium", "low", "info"],
                    ),
                    "category": types.Schema(
                        type="STRING",
                        description=(
                            "e.g. sql_injection, xss, missing_auth, idor, "
                            "cors_misconfiguration, exposed_endpoint, missing_headers, "
                            "information_disclosure, default_credentials, command_injection"
                        ),
                    ),
                    "title": types.Schema(type="STRING", description="Short one-line summary"),
                    "description": types.Schema(
                        type="STRING",
                        description="2-3 sentences: vulnerability, what you tested, impact",
                    ),
                    "evidence": types.Schema(
                        type="OBJECT",
                        description="Evidence: {payload, response_code, response_preview, url}",
                    ),
                    "remediation": types.Schema(
                        type="STRING", description="Specific actionable fix"
                    ),
                },
                required=["severity", "category", "title", "description", "remediation"],
            ),
        ),
    ])
]


class BaseAgent:
    """
    Runs a Gemini function-calling loop that iteratively probes
    the target application and reports findings.
    """

    name: str = "base"

    def __init__(
        self,
        assessment_id: str,
        target_url: str,
        depth: str,
        db_session,
        coverage_context: dict | None = None,
    ):
        self.assessment_id = assessment_id
        self.target_url = target_url.rstrip("/")
        self.depth = depth
        self.max_steps = {"quick": 10, "standard": 28, "deep": 55}.get(depth, 28)
        self.max_http_requests = {"quick": 30, "standard": 85, "deep": 170}.get(depth, 85)
        self.per_path_limit = {"quick": 2, "standard": 3, "deep": 4}.get(depth, 3)
        self.db = db_session
        self.findings: list[Finding] = []
        self.step_count = 0
        self.http_request_count = 0
        self.path_attempts: dict[str, int] = {}
        self.coverage_context = coverage_context or {}
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL or "gemini-2.5-flash"

    async def run(self) -> list[Finding]:
        system_prompt = self._get_system_prompt()
        initial_message = (
            f"Target URL: {self.target_url}\n"
            f"Max steps: {self.max_steps}\n"
            f"Max HTTP requests: {self.max_http_requests}\n"
            f"Depth: {self.depth}\n\n"
            f"Discovered seed paths: {json.dumps(self.coverage_context.get('seed_paths', [])[:60])}\n"
            f"Reachable paths (status): {json.dumps(self.coverage_context.get('reachable_paths', [])[:60])}\n"
            f"Interesting request samples: {json.dumps(self.coverage_context.get('request_samples', [])[:20])}\n\n"
            f"Begin your security assessment. Use your tools to probe the target. "
            f"Call report_finding for each confirmed vulnerability with evidence.\n"
            f"Prioritize breadth first: cover distinct endpoints and input points before deep repetition."
        )

        contents = [types.Content(role="user", parts=[types.Part(text=initial_message)])]

        while self.step_count < self.max_steps:
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=AGENT_TOOLS,
                        temperature=0.2,
                    ),
                )
            except Exception as e:
                raise RuntimeError(f"[{self.name}] Gemini generate_content failed: {e}") from e

            candidate = response.candidates[0] if response.candidates else None
            if not candidate or not candidate.content or not candidate.content.parts:
                break

            parts = candidate.content.parts
            function_calls = [p for p in parts if p.function_call]

            if not function_calls:
                break

            contents.append(candidate.content)

            function_responses = []
            for part in function_calls:
                fc = part.function_call
                tool_result = await self._execute_tool(
                    fc.name, dict(fc.args) if fc.args else {}
                )
                function_responses.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            name=fc.name,
                            response={"result": tool_result},
                        )
                    )
                )

            contents.append(types.Content(role="user", parts=function_responses))

        return self.findings

    async def _execute_tool(self, name: str, args: dict) -> dict:
        if name == "http_request":
            method = args.get("method", "GET")
            path = args.get("path", "/")
            headers = args.get("headers")
            body = args.get("body")

            if not path.startswith("/"):
                path = f"/{path}"

            if self.http_request_count >= self.max_http_requests:
                return {
                    "error": "request_budget_exceeded",
                    "message": (
                        f"Request budget exceeded for this agent "
                        f"({self.max_http_requests}). Prioritize reporting findings."
                    ),
                }

            path_key = f"{method.upper()} {path}"
            prior_attempts = self.path_attempts.get(path_key, 0)
            if prior_attempts >= self.per_path_limit:
                return {
                    "error": "path_attempt_limit_reached",
                    "message": (
                        f"Path attempt limit reached for {path_key}. "
                        "Try a different endpoint or attack path."
                    ),
                }

            self.path_attempts[path_key] = prior_attempts + 1
            self.http_request_count += 1

            result = await http_request(self.target_url, method, path, headers, body)
            await self._log_step(
                action=f"{method} {path}",
                target=path,
                payload=body,
                response_code=result.get("status_code"),
                response_preview=result.get("body_preview", result.get("message", ""))[:500],
                reasoning=f"Probing {path} with {method}",
            )
            return result

        elif name == "check_headers":
            path = args.get("path", "/")
            result = await check_security_headers(self.target_url, path)
            await self._log_step(
                action=f"Check security headers on {path}",
                target=path,
                payload=None,
                response_code=None,
                response_preview=json.dumps(result.get("issues", []))[:500],
                reasoning="Analyzing security headers",
            )
            return result

        elif name == "report_finding":
            finding = await self._save_finding(args)
            return {"status": "finding_reported", "finding_id": finding.id}

        return {"error": f"Unknown tool: {name}"}

    async def _log_step(
        self,
        action: str,
        target: str,
        payload: str | None,
        response_code: int | None,
        response_preview: str | None,
        reasoning: str,
        finding_id: str | None = None,
    ):
        self.step_count += 1
        log = AgentLog(
            id=generate_id("log"),
            assessment_id=self.assessment_id,
            agent=self.name,
            step=self.step_count,
            action=action,
            target=target,
            payload=payload,
            response_code=response_code,
            response_preview=response_preview,
            reasoning=reasoning,
            finding_id=finding_id,
            timestamp=datetime.utcnow(),
        )
        self.db.add(log)
        await self.db.flush()

    async def _save_finding(self, data: dict) -> Finding:
        evidence = data.get("evidence")
        location = None
        if isinstance(evidence, dict) and "url" in evidence:
            location = {"type": "endpoint", "url": evidence["url"]}

        finding = Finding(
            id=generate_id("fnd"),
            assessment_id=self.assessment_id,
            severity=data.get("severity", "info"),
            category=data.get("category", "unknown"),
            title=data.get("title", "Untitled finding"),
            description=data.get("description", ""),
            location=location,
            evidence=evidence,
            remediation=data.get("remediation", ""),
            agent=self.name,
            created_at=datetime.utcnow(),
        )
        self.db.add(finding)
        await self.db.flush()
        self.findings.append(finding)

        await SupermemoryService.ingest_finding(
            assessment_id=self.assessment_id,
            mode="robust",
            repo_url=None,
            target_url=self.target_url,
            finding={
                "severity": finding.severity,
                "category": finding.category,
                "title": finding.title,
                "description": finding.description,
                "location": finding.location,
                "remediation": finding.remediation,
            },
        )

        await self._log_step(
            action=f"Reported {data.get('severity', 'info')} finding: {data.get('title', '')}",
            target=evidence.get("url", "") if isinstance(evidence, dict) else "",
            payload=None,
            response_code=None,
            response_preview=data.get("description", "")[:500],
            reasoning=f"Confirmed vulnerability: {data.get('category', '')}",
            finding_id=finding.id,
        )
        return finding

    def _get_system_prompt(self) -> str:
        raise NotImplementedError
