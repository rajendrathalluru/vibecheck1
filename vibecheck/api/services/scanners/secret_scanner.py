import math
import re

SECRET_PATTERNS = [
    (r'''(?:api[_-]?key|apikey)\s*[:=]\s*['"]([A-Za-z0-9_\-]{20,})['"]''', "API key"),
    (r'''AKIA[0-9A-Z]{16}''', "AWS Access Key ID"),
    (r'''(?:aws[_-]?secret|AWS_SECRET_ACCESS_KEY)\s*[:=]\s*['"]([A-Za-z0-9/+=]{40})['"]''', "AWS Secret Access Key"),
    (r'''gh[ps]_[A-Za-z0-9_]{36,}''', "GitHub token"),
    (r'''github_pat_[A-Za-z0-9_]{22,}''', "GitHub Personal Access Token"),
    (r'''sk_live_[A-Za-z0-9]{24,}''', "Stripe Secret Key (LIVE)"),
    (r'''sk_test_[A-Za-z0-9]{24,}''', "Stripe Secret Key (test)"),
    (r'''xox[baprs]-[A-Za-z0-9\-]{10,}''', "Slack token"),
    (r'''(?:secret|password|passwd|pwd|token|auth_token|access_token|private_key)\s*[:=]\s*['"]([^'"]{8,})['"]''', "Hardcoded secret"),
    (r'''(?:jwt[_-]?secret|JWT_SECRET)\s*[:=]\s*['"]([^'"]{6,})['"]''', "JWT Secret"),
    (r'''(?:postgres|mysql|mongodb|redis)(?:ql)?:\/\/\w+:[^@\s]+@''', "Database URL with credentials"),
    (r'''-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----''', "Private key"),
    (r'''SG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}''', "SendGrid API key"),
    (r'''AC[a-f0-9]{32}''', "Twilio Account SID"),
    (r'''AIza[0-9A-Za-z\-_]{35}''', "Google API key"),
]

SKIP_PATTERNS = [
    r"\.test\.",
    r"\.spec\.",
    r"__test__",
    r"\.example$",
    r"\.sample$",
    r"package-lock\.json$",
    r"yarn\.lock$",
    r"\.lock$",
    r"\.min\.js$",
    r"node_modules",
    r"vendor/",
]


def scan(files: list[dict]) -> list[dict]:
    """Detect hardcoded secrets in source files."""
    findings = []

    for f in files:
        path = f["path"]
        if any(re.search(pat, path) for pat in SKIP_PATTERNS):
            continue

        lines = f["content"].splitlines()
        for i, line in enumerate(lines, 1):
            for pattern, secret_type in SECRET_PATTERNS:
                try:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        matched_text = match.group(0)
                        if _is_placeholder(matched_text):
                            continue

                        severity = "critical"
                        if "test" in secret_type.lower():
                            severity = "high"

                        findings.append({
                            "severity": severity,
                            "category": "hardcoded_secret",
                            "title": f"{secret_type} found in {path}",
                            "description": (
                                f"A hardcoded {secret_type} was detected. Hardcoded secrets in source code "
                                "can be extracted by anyone with repo access and are difficult to rotate."
                            ),
                            "location": {
                                "type": "file",
                                "file": path,
                                "line": i,
                                "snippet": _redact_secret(line.strip(), match),
                            },
                            "evidence": {"secret_type": secret_type, "pattern_matched": True},
                            "remediation": (
                                "Move secrets to environment variables. Use a secrets manager "
                                "(e.g., AWS Secrets Manager, HashiCorp Vault, or .env files excluded from version control)."
                            ),
                        })
                        break  # One finding per line
                except re.error:
                    continue

    # High-entropy string check on secret-context assignments
    for f in files:
        if any(re.search(pat, f["path"]) for pat in SKIP_PATTERNS):
            continue
        ext = "." + f["path"].rsplit(".", 1)[-1] if "." in f["path"] else ""
        if ext in {".json", ".lock", ".svg", ".map"}:
            continue

        lines = f["content"].splitlines()
        for i, line in enumerate(lines, 1):
            assign_match = re.search(
                r'''(?:secret|key|token|password|pwd)\s*[:=]\s*['"]([A-Za-z0-9+/=_\-]{20,})['"]''',
                line,
                re.IGNORECASE,
            )
            if assign_match:
                value = assign_match.group(1)
                if _shannon_entropy(value) > 4.0 and not _is_placeholder(value):
                    already_found = any(
                        fd.get("location", {}).get("file") == f["path"]
                        and fd.get("location", {}).get("line") == i
                        for fd in findings
                    )
                    if not already_found:
                        findings.append({
                            "severity": "high",
                            "category": "hardcoded_secret",
                            "title": f"High-entropy secret in {f['path']}",
                            "description": (
                                "A high-entropy string was found in a secret/key/token/password assignment. "
                                "This likely contains a real credential."
                            ),
                            "location": {
                                "type": "file",
                                "file": f["path"],
                                "line": i,
                                "snippet": _redact_secret(line.strip(), assign_match),
                            },
                            "evidence": {
                                "entropy": round(_shannon_entropy(value), 2),
                                "length": len(value),
                            },
                            "remediation": "Move this value to an environment variable or secrets manager.",
                        })

    return findings


def _is_placeholder(text: str) -> bool:
    placeholders = [
        "your_", "example", "placeholder", "changeme", "xxx", "todo",
        "replace", "insert", "dummy", "fake", "sample", "test_",
        "sk_test_", "pk_test_", "CHANGE_ME", "<your", "${", "{{",
        "process.env", "os.environ", "os.getenv", "ENV[",
    ]
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in placeholders)


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for c in s:
        freq[c] = freq.get(c, 0) + 1
    length = len(s)
    return -sum(
        (count / length) * math.log2(count / length) for count in freq.values()
    )


def _redact_secret(line: str, match: re.Match) -> str:
    start, end = match.span()
    secret = line[start:end]
    if len(secret) > 8:
        redacted = secret[:4] + "*" * (len(secret) - 8) + secret[-4:]
    else:
        redacted = "****"
    return line[:start] + redacted + line[end:]
