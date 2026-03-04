const testerEls = {
  form: document.getElementById("testerForm"),
  baseUrl: document.getElementById("testerBaseUrl"),
  method: document.getElementById("testerMethod"),
  path: document.getElementById("testerPath"),
  body: document.getElementById("testerBody"),
  status: document.getElementById("testerStatus"),
  response: document.getElementById("testerResponse"),
  loadHealth: document.getElementById("testerLoadHealth"),
  loadCreate: document.getElementById("testerLoadCreate"),
};

function normalizeBaseUrl(url) {
  return (url || "").trim().replace(/\/$/, "");
}

function setExample(method, path, body) {
  testerEls.method.value = method;
  testerEls.path.value = path;
  testerEls.body.value = body;
}

function renderResponse(status, headers, bodyText) {
  testerEls.response.textContent = [
    `HTTP ${status}`,
    "",
    "Headers:",
    headers,
    "",
    "Body:",
    bodyText,
  ].join("\n");
}

async function runRequest(event) {
  event.preventDefault();

  const baseUrl = normalizeBaseUrl(testerEls.baseUrl.value);
  const method = testerEls.method.value;
  const path = testerEls.path.value.trim();

  if (!baseUrl || !path.startsWith("/")) {
    testerEls.status.textContent = "Use a valid API base URL and a path starting with /";
    return;
  }

  const url = `${baseUrl}${path}`;
  const options = { method, headers: { Accept: "application/json" } };

  if (method === "POST") {
    const raw = testerEls.body.value.trim();
    if (raw) {
      try {
        JSON.parse(raw);
      } catch {
        testerEls.status.textContent = "Invalid JSON body. Fix JSON and retry.";
        return;
      }
      options.headers["Content-Type"] = "application/json";
      options.body = raw;
    }
  }

  testerEls.status.textContent = `Sending ${method} ${path}...`;

  try {
    const response = await fetch(url, options);
    const text = await response.text();
    const headerDump = Array.from(response.headers.entries())
      .map(([key, value]) => `${key}: ${value}`)
      .join("\n");
    let prettyBody = text;
    try {
      prettyBody = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      // Keep text as-is if not JSON.
    }
    renderResponse(response.status, headerDump || "(none)", prettyBody || "(empty)");
    testerEls.status.textContent = response.ok ? "Request completed." : `Request failed (${response.status}).`;
  } catch (error) {
    testerEls.status.textContent = `Network error: ${error.message}`;
    testerEls.response.textContent = "No response received.";
  }
}

function initDocsTester() {
  const sameOrigin = window.location.origin && window.location.origin !== "null";
  testerEls.baseUrl.value = sameOrigin ? window.location.origin : "https://vibecheck.aedify.ai";

  setExample("GET", "/v1/health", "");

  testerEls.form.addEventListener("submit", runRequest);
  testerEls.loadHealth.addEventListener("click", () => setExample("GET", "/v1/health", ""));
  testerEls.loadCreate.addEventListener("click", () =>
    setExample(
      "POST",
      "/v1/assessments",
      JSON.stringify(
        {
          mode: "lightweight",
          repo_url: "https://github.com/vulnerable-apps/damn-vulnerable-MCP-server",
        },
        null,
        2,
      ),
    ),
  );
}

initDocsTester();
