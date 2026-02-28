import re

# (regex, severity, category, title_template, description, remediation)
# {file} is replaced at match time
PATTERNS = [
    # SQL Injection
    (
        r'''(?:query|execute|exec|raw)\s*\(\s*[`"']?\s*(?:SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE).*?(?:\+\s*\w|\$\{|\%s|%\()''',
        "critical", "sql_injection",
        "Potential SQL injection in {file}",
        "Raw SQL query with dynamic input detected. String concatenation or template literals in SQL queries allow attackers to inject arbitrary SQL.",
        "Use parameterized queries or an ORM. Never concatenate user input into SQL strings.",
    ),
    (
        r'''\.raw\s*\(.*[\+\$\%]''',
        "critical", "sql_injection",
        "Raw query with dynamic input in {file}",
        "ORM .raw() method called with dynamic input. This bypasses the ORM's built-in protections.",
        "Use the ORM's query builder instead of .raw() with string interpolation.",
    ),
    (
        r'''f["\'].*(?:SELECT|INSERT|UPDATE|DELETE)\s+.*\{.*\}''',
        "critical", "sql_injection",
        "f-string SQL query in {file}",
        "Python f-string used to build a SQL query with embedded variables. This is a direct SQL injection vector.",
        "Use parameterized queries with placeholders (e.g., cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))).",
    ),
    # XSS
    (
        r'''\.innerHTML\s*=\s*(?!['"`]\s*['"`])''',
        "high", "xss",
        "innerHTML assignment in {file}",
        "Direct innerHTML assignment with dynamic content. If user input reaches this, it enables cross-site scripting.",
        "Use textContent instead of innerHTML, or sanitize with DOMPurify.",
    ),
    (
        r'''dangerouslySetInnerHTML''',
        "high", "xss",
        "dangerouslySetInnerHTML in {file}",
        "React's dangerouslySetInnerHTML used. This bypasses React's XSS protections.",
        "Avoid dangerouslySetInnerHTML. If necessary, sanitize input with DOMPurify before rendering.",
    ),
    (
        r'''v-html\s*=''',
        "high", "xss",
        "v-html directive in {file}",
        "Vue's v-html directive renders raw HTML. If user input is rendered, this is an XSS vector.",
        "Use v-text or {{ }} interpolation instead. Sanitize if v-html is truly needed.",
    ),
    # Dangerous functions
    (
        r'''\beval\s*\(''',
        "critical", "code_injection",
        "eval() usage in {file}",
        "eval() executes arbitrary code. If user input reaches eval, it enables remote code execution.",
        "Remove eval(). Use JSON.parse() for data, or a sandboxed interpreter if dynamic execution is truly needed.",
    ),
    (
        r'''\bexec\s*\(''',
        "critical", "code_injection",
        "exec() usage in {file}",
        "exec() executes arbitrary Python code. This is extremely dangerous if any user input is involved.",
        "Remove exec(). Use safer alternatives like ast.literal_eval() for data parsing.",
    ),
    (
        r'''new\s+Function\s*\(''',
        "critical", "code_injection",
        "new Function() constructor in {file}",
        "The Function constructor compiles and executes code from strings, similar to eval().",
        "Avoid the Function constructor. Use static function definitions.",
    ),
    (
        r'''child_process\.exec\s*\(''',
        "critical", "command_injection",
        "child_process.exec in {file}",
        "child_process.exec runs shell commands. If user input is included, it enables OS command injection.",
        "Use child_process.execFile() with an argument array instead of exec() with a command string.",
    ),
    (
        r'''subprocess\.(?:call|run|Popen)\s*\(\s*(?:[^,\]]*\+|f["\']|.*\.format|.*\%)''',
        "critical", "command_injection",
        "subprocess with dynamic input in {file}",
        "subprocess called with string concatenation or formatting. This can enable OS command injection.",
        "Use subprocess with a list of arguments: subprocess.run(['cmd', arg1, arg2]) instead of a formatted string.",
    ),
    (
        r'''os\.system\s*\(''',
        "critical", "command_injection",
        "os.system() usage in {file}",
        "os.system() runs shell commands and is vulnerable to injection. It also doesn't capture output.",
        "Use subprocess.run() with a list of arguments instead of os.system().",
    ),
    # Insecure deserialization
    (
        r'''pickle\.loads?\s*\(''',
        "critical", "insecure_deserialization",
        "pickle.load/loads in {file}",
        "Python pickle deserializes arbitrary objects. Loading untrusted pickle data can execute arbitrary code.",
        "Use JSON or another safe serialization format. If pickle is required, only load data from fully trusted sources.",
    ),
    (
        r'''yaml\.load\s*\([^)]*\)(?!.*Loader\s*=\s*(?:yaml\.)?SafeLoader)''',
        "critical", "insecure_deserialization",
        "Unsafe yaml.load() in {file}",
        "yaml.load() without SafeLoader can execute arbitrary Python code embedded in YAML.",
        "Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
    ),
    # Missing input validation
    (
        r'''req\.(?:params|query|body)\.\w+(?!\s*\?\.)(?!.*(?:parseInt|Number|validate|sanitize|escape|trim|zod|yup|joi))''',
        "medium", "missing_validation",
        "Unvalidated request input in {file}",
        "Request parameter accessed without visible validation or sanitization.",
        "Validate and sanitize all request inputs. Use a validation library like Zod, Joi, or Yup.",
    ),
    # Debug mode
    (
        r'''(?:debug|DEBUG)\s*[:=]\s*(?:true|True|1|"true")''',
        "medium", "debug_mode",
        "Debug mode enabled in {file}",
        "Debug mode is enabled. This may expose stack traces, internal paths, and sensitive configuration.",
        "Disable debug mode in production. Use environment variables to control debug settings.",
    ),
    (
        r'''app\.run\s*\(.*debug\s*=\s*True''',
        "medium", "debug_mode",
        "Flask debug mode in {file}",
        "Flask app.run() called with debug=True. This enables the Werkzeug debugger which allows arbitrary code execution.",
        "Set debug=False in production. Use environment variable: app.run(debug=os.environ.get('DEBUG', False)).",
    ),
    # CORS
    (
        r'''(?:Access-Control-Allow-Origin|cors)\s*[:=]\s*['"]\*['"]''',
        "medium", "cors_misconfiguration",
        "Wildcard CORS in {file}",
        "CORS is configured to allow all origins (*). This permits any website to make authenticated requests to your API.",
        "Restrict CORS to specific trusted origins instead of using wildcard.",
    ),
    (
        r'''cors\(\s*\)(?!\s*\()''',
        "medium", "cors_misconfiguration",
        "Default CORS (allow all) in {file}",
        "CORS middleware initialized without options, which may default to allowing all origins.",
        "Configure CORS with specific origins: cors({origin: ['https://yourdomain.com']}).",
    ),
    # Logging sensitive data
    (
        r'''console\.log\s*\(.*(?:password|token|secret|key|auth|credential|ssn|credit.?card)''',
        "low", "information_disclosure",
        "Sensitive data in console.log in {file}",
        "Sensitive data (passwords, tokens, secrets) appears to be logged to console.",
        "Remove logging of sensitive data. Use structured logging with redaction for production.",
    ),
    (
        r'''(?:print|logging\.(?:debug|info|warning))\s*\(.*(?:password|token|secret|key|auth|credential)''',
        "low", "information_disclosure",
        "Sensitive data logged in {file}",
        "Sensitive data appears in print/logging statements.",
        "Remove sensitive data from log statements. Use structured logging with automatic redaction.",
    ),
]

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte", ".rb", ".php", ".java", ".go",
}


def scan(files: list[dict]) -> list[dict]:
    """Run regex patterns against all source files."""
    findings = []

    for f in files:
        ext = "." + f["path"].rsplit(".", 1)[-1] if "." in f["path"] else ""
        if ext not in CODE_EXTENSIONS:
            continue

        lines = f["content"].splitlines()
        for pattern, severity, category, title_tpl, description, remediation in PATTERNS:
            try:
                for i, line in enumerate(lines, 1):
                    if re.search(pattern, line, re.IGNORECASE):
                        findings.append({
                            "severity": severity,
                            "category": category,
                            "title": title_tpl.format(file=f["path"]),
                            "description": description,
                            "location": {
                                "type": "file",
                                "file": f["path"],
                                "line": i,
                                "snippet": line.strip()[:200],
                            },
                            "remediation": remediation,
                        })
                        break  # One finding per pattern per file
            except re.error:
                continue

    return findings
