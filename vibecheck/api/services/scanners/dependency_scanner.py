VULN_DB = {
    # JavaScript / Node.js
    "express": [("<", "4.19.2", "high", "CVE-2024-29041", "Open redirect vulnerability in express")],
    "jsonwebtoken": [("<", "9.0.0", "critical", "CVE-2022-23529", "JWT verification bypass allows arbitrary code execution")],
    "lodash": [("<", "4.17.21", "critical", "CVE-2021-23337", "Prototype pollution via zipObjectDeep")],
    "axios": [("<", "1.6.0", "high", "CVE-2023-45857", "SSRF via server-side request forgery")],
    "node-fetch": [("<", "2.6.7", "high", "CVE-2022-0235", "Exposure of sensitive information to unauthorized actor")],
    "minimist": [("<", "1.2.6", "critical", "CVE-2021-44906", "Prototype pollution")],
    "qs": [("<", "6.10.3", "high", "CVE-2022-24999", "Prototype pollution via __proto__ parameter")],
    "tar": [("<", "6.1.9", "high", "CVE-2021-37712", "Arbitrary file creation/overwrite via symlink")],
    "glob-parent": [("<", "5.1.2", "high", "CVE-2020-28469", "Regular expression denial of service")],
    "next": [("<", "14.1.1", "high", "CVE-2024-34351", "Server-side request forgery in Server Actions")],
    "sequelize": [("<", "6.33.0", "high", "CVE-2023-22578", "SQL injection via replacements")],
    "mysql2": [("<", "3.6.0", "critical", "CVE-2024-21511", "Remote code execution via prototype poisoning")],
    "helmet": [("<", "7.0.0", "medium", "N/A", "Outdated security headers configuration")],
    "cors": [("<", "2.8.5", "medium", "N/A", "CORS misconfiguration possible in older versions")],
    "passport": [("<", "0.6.0", "high", "CVE-2022-25896", "Session fixation attack")],
    # Python
    "flask": [("<", "2.3.2", "high", "CVE-2023-30861", "Session cookie set without Secure flag on non-HTTPS")],
    "django": [("<", "4.2.4", "high", "CVE-2023-36053", "Potential ReDoS in EmailValidator/URLValidator")],
    "pyyaml": [("<", "6.0", "critical", "CVE-2020-14343", "Arbitrary code execution via yaml.load")],
    "requests": [("<", "2.31.0", "medium", "CVE-2023-32681", "Unintended leak of Proxy-Authorization header")],
    "urllib3": [("<", "2.0.6", "medium", "CVE-2023-43804", "Cookie header leak on cross-origin redirects")],
    "pillow": [("<", "10.0.1", "high", "CVE-2023-44271", "Denial of service via large image")],
    "cryptography": [("<", "41.0.4", "high", "CVE-2023-38325", "NULL dereference in PKCS7 parsing")],
    "jinja2": [("<", "3.1.3", "medium", "CVE-2024-22195", "XSS via xmlattr filter")],
    "sqlalchemy": [("<", "2.0.0", "medium", "N/A", "Legacy query interface prone to injection patterns")],
    "werkzeug": [("<", "2.3.8", "high", "CVE-2023-46136", "Denial of service via multipart parser")],
}


def scan(files: list[dict], project_info: dict) -> list[dict]:
    """Check project dependencies against known vulnerable versions."""
    findings = []
    deps = project_info.get("dependencies", {})

    for pkg_name, version_str in deps.items():
        pkg_lower = pkg_name.lower().strip()
        if pkg_lower not in VULN_DB:
            continue

        for op, vuln_version, severity, cve, description in VULN_DB[pkg_lower]:
            clean_version = version_str.lstrip("^~>=<! ")
            if clean_version == "*" or not clean_version:
                findings.append({
                    "severity": "info",
                    "category": "vulnerable_dependency",
                    "title": f"Unpinned dependency: {pkg_name}",
                    "description": (
                        f"Package '{pkg_name}' has no pinned version. "
                        f"Known vulnerability exists in versions {op} {vuln_version}: {description}"
                    ),
                    "location": {"type": "dependency", "package": pkg_name, "version": version_str},
                    "evidence": {"cve": cve, "vulnerable_below": vuln_version},
                    "remediation": f"Pin {pkg_name} to version {vuln_version} or later.",
                })
                continue

            if _is_version_vulnerable(clean_version, op, vuln_version):
                findings.append({
                    "severity": severity,
                    "category": "vulnerable_dependency",
                    "title": f"Vulnerable dependency: {pkg_name}@{version_str}",
                    "description": (
                        f"{description}. Installed version {version_str} is vulnerable "
                        f"(affects versions {op} {vuln_version})."
                    ),
                    "location": {"type": "dependency", "package": pkg_name, "version": version_str},
                    "evidence": {"cve": cve, "vulnerable_below": vuln_version, "installed_version": version_str},
                    "remediation": f"Upgrade {pkg_name} to version {vuln_version} or later.",
                })

    return findings


def _is_version_vulnerable(installed: str, operator: str, vuln_version: str) -> bool:
    """Simple semver comparison for major.minor.patch format."""
    try:
        installed_parts = [int(x) for x in installed.split(".")[:3]]
        vuln_parts = [int(x) for x in vuln_version.split(".")[:3]]
        while len(installed_parts) < 3:
            installed_parts.append(0)
        while len(vuln_parts) < 3:
            vuln_parts.append(0)

        if operator == "<":
            return installed_parts < vuln_parts
        elif operator == "<=":
            return installed_parts <= vuln_parts
        return False
    except (ValueError, AttributeError):
        return False
