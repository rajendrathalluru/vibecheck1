import re


def scan(files: list[dict], project_info: dict) -> list[dict]:
    """Analyze configuration files for security misconfigurations."""
    findings = []

    has_env_file = any(
        f["path"] == ".env" or f["path"].endswith("/.env")
        for f in files
    )
    gitignore_entries = project_info.get("gitignore_entries", [])
    env_in_gitignore = any(
        entry in (".env", ".env*", ".env.*", "*.env")
        for entry in gitignore_entries
    )

    if has_env_file and not env_in_gitignore:
        findings.append({
            "severity": "critical",
            "category": "exposed_secrets",
            "title": ".env file not in .gitignore",
            "description": (
                "An .env file exists but is not listed in .gitignore. If committed, "
                "environment variables (database URLs, API keys, secrets) will be exposed in version control history."
            ),
            "location": {"type": "file", "file": ".gitignore"},
            "remediation": (
                "Add '.env' to .gitignore immediately. If already committed, rotate all secrets "
                "in the .env file and use 'git filter-branch' or BFG to remove it from history."
            ),
        })

    if not project_info.get("has_gitignore"):
        findings.append({
            "severity": "high",
            "category": "missing_gitignore",
            "title": "No .gitignore file found",
            "description": (
                "No .gitignore file was detected. This risks committing sensitive files, "
                "build artifacts, and dependencies to version control."
            ),
            "location": {"type": "file", "file": ".gitignore"},
            "remediation": "Create a .gitignore file. Use gitignore.io to generate one for your language/framework.",
        })

    # Dockerfile issues
    for f in files:
        if "Dockerfile" not in f["path"]:
            continue
        content = f["content"]

        if re.search(r"USER\s+root", content) or not re.search(r"USER\s+\w+", content):
            findings.append({
                "severity": "medium",
                "category": "container_security",
                "title": f"Container runs as root in {f['path']}",
                "description": (
                    "Dockerfile does not specify a non-root USER. Container processes running "
                    "as root can escalate to host-level access if the container is compromised."
                ),
                "location": {"type": "file", "file": f["path"]},
                "remediation": "Add 'RUN adduser --disabled-password appuser' and 'USER appuser' to your Dockerfile.",
            })

        if re.search(r"COPY\s+\.env", content):
            findings.append({
                "severity": "critical",
                "category": "exposed_secrets",
                "title": f".env file copied into Docker image in {f['path']}",
                "description": (
                    "The .env file is being COPY'd into the Docker image. "
                    "Anyone with access to the image can extract all secrets."
                ),
                "location": {"type": "file", "file": f["path"]},
                "remediation": (
                    "Use Docker secrets or pass environment variables at runtime with "
                    "'docker run -e' or '--env-file'. Add .env to .dockerignore."
                ),
            })

    # Next.js config
    for f in files:
        if "next.config" not in f["path"]:
            continue
        content = f["content"]

        if re.search(r"reactStrictMode\s*:\s*false", content):
            findings.append({
                "severity": "low",
                "category": "framework_config",
                "title": "React Strict Mode disabled in Next.js",
                "description": "React Strict Mode is disabled. It helps identify unsafe lifecycles and deprecated patterns.",
                "location": {"type": "file", "file": f["path"]},
                "remediation": "Set reactStrictMode: true in next.config.js.",
            })

        if re.search(r"(?:images|remotePatterns).*\*", content, re.DOTALL):
            findings.append({
                "severity": "medium",
                "category": "framework_config",
                "title": "Wildcard image domains in Next.js",
                "description": (
                    "Next.js image optimization is configured with wildcard domains. "
                    "This allows loading images from any external source."
                ),
                "location": {"type": "file", "file": f["path"]},
                "remediation": "Restrict image domains to specific trusted sources.",
            })

    # Package.json lifecycle scripts
    for f in files:
        if f["path"] != "package.json" and not f["path"].endswith("/package.json"):
            continue
        content = f["content"]

        if '"postinstall"' in content or '"preinstall"' in content:
            findings.append({
                "severity": "info",
                "category": "supply_chain",
                "title": "Install lifecycle scripts detected",
                "description": (
                    "package.json contains pre/post install scripts. These run automatically on "
                    "'npm install' and could execute malicious code if a dependency is compromised."
                ),
                "location": {"type": "file", "file": f["path"]},
                "remediation": "Audit install scripts. Consider using --ignore-scripts flag or npm's 'allow-scripts' feature.",
            })

    # Docker-compose exposed ports
    for f in files:
        if "docker-compose" not in f["path"]:
            continue
        content = f["content"]

        if re.search(r"ports:\s*\n\s*-\s*[\"']?0\.0\.0\.0:", content):
            findings.append({
                "severity": "medium",
                "category": "network_exposure",
                "title": f"Service bound to all interfaces in {f['path']}",
                "description": (
                    "A service is bound to 0.0.0.0, making it accessible from any "
                    "network interface, not just localhost."
                ),
                "location": {"type": "file", "file": f["path"]},
                "remediation": "Bind to 127.0.0.1 for services that should only be accessed locally.",
            })

    return findings
