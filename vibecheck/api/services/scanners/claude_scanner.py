import json

from openai import AsyncOpenAI

from api.config import settings

PRIORITY_KEYWORDS = [
    "route",
    "api",
    "auth",
    "login",
    "middleware",
    "db",
    "database",
    "config",
    "server",
    "app",
]


async def scan(files: list[dict], project_info: dict) -> list[dict]:
    """Use an LLM (OpenAI) to perform contextual security analysis."""
    if not settings.OPENAI_API_KEY:
        return []

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    file_summaries: list[str] = []
    total_chars = 0
    max_chars = 50_000

    sorted_files = sorted(
        files,
        key=lambda f: -sum(1 for p in PRIORITY_KEYWORDS if p in f["path"].lower()),
    )

    for f in sorted_files:
        entry = f"### {f['path']}\n```\n{f['content']}\n```\n"
        if total_chars + len(entry) > max_chars:
            break
        file_summaries.append(entry)
        total_chars += len(entry)

    if not file_summaries:
        return []

    codebase = "\n".join(file_summaries)
    language = project_info.get("language", "unknown")
    framework = project_info.get("framework", "unknown")

    prompt = f"""You are a senior application security engineer performing a code review. Analyze this {language}/{framework} codebase for security vulnerabilities that automated regex scanning would miss.

Focus on:
1. Business logic flaws - auth bypass through logic errors, race conditions, TOCTOU bugs
2. Authentication/authorization design - missing auth checks on sensitive routes, broken access control, privilege escalation paths
3. Data exposure - API endpoints returning sensitive fields (passwords, tokens, internal IDs), verbose error messages leaking internals
4. Framework-specific issues - misuse of {framework} security features, missing CSRF protection, insecure session config
5. Cryptographic issues - weak hashing (MD5/SHA1 for passwords), predictable tokens, missing encryption
6. Input handling - missing validation on critical fields, type confusion, mass assignment

Do NOT report:
- Issues that a regex scanner would catch (obvious SQL injection, hardcoded secrets with clear patterns)
- Generic best-practice suggestions without specific code evidence
- Issues in test files

Respond ONLY with a JSON array. Each finding must have:
- "severity": "critical" | "high" | "medium" | "low" | "info"
- "category": short snake_case category
- "title": one-line summary
- "description": 2-3 sentences explaining the vulnerability and its impact
- "location": {{"file": "path/to/file", "line": approximate_line_number}} (if identifiable)
- "remediation": specific actionable fix

If you find no issues, return an empty array: []

Codebase:
{codebase}"""

    try:
        response = await client.responses.create(
            model=settings.OPENAI_MODEL,
            input=prompt,
        )

        # Responses API: text is in response.output[0].content[0].text
        text = response.output[0].content[0].text.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        findings_data = json.loads(text)
        if not isinstance(findings_data, list):
            return []

        findings: list[dict] = []
        required_fields = {"severity", "category", "title", "description", "remediation"}
        valid_severities = {"critical", "high", "medium", "low", "info"}

        for item in findings_data:
            if not required_fields.issubset(item.keys()):
                continue
            if item["severity"] not in valid_severities:
                continue

            findings.append(
                {
                    "severity": item["severity"],
                    "category": item["category"],
                    "title": item["title"],
                    "description": item["description"],
                    "location": item.get("location"),
                    "remediation": item["remediation"],
                }
            )

        return findings

    except Exception:
        # On any error (bad JSON, API failure, etc.), fall back silently to no LLM findings.
        return []
