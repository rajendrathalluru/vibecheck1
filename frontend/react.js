import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);
const AGENTS = ["recon", "auth", "injection", "config"];
const ACTIVE_STATUSES = new Set(["queued", "cloning", "analyzing", "scanning"]);
const SEVERITY_ORDER = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };

function formatDate(ts) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function badgeClass(prefix, value) {
  return `${prefix}-${String(value || "unknown").toLowerCase()}`;
}

function downloadFile(name, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  if (value == null) return "";
  return `"${String(value).replace(/"/g, "\"\"")}"`;
}

function App() {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8000");
  const [status, setStatus] = useState("Ready.");
  const [autoPoll, setAutoPoll] = useState(false);
  const [mode, setMode] = useState("lightweight");
  const [repoUrl, setRepoUrl] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [depth, setDepth] = useState("standard");
  const [selectedAgents, setSelectedAgents] = useState(new Set(AGENTS));

  const [assessments, setAssessments] = useState([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState(null);
  const [asmPage, setAsmPage] = useState(1);
  const asmPerPage = 12;

  const [findings, setFindings] = useState([]);
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [findingPage, setFindingPage] = useState(1);
  const findingPerPage = 12;
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");

  async function apiFetch(path, options = {}) {
    const url = `${apiBase.trim().replace(/\/$/, "")}${path}`;
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        message = body?.error?.message || JSON.stringify(body);
      } catch {
        // Keep default.
      }
      throw new Error(message);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  async function loadAssessments() {
    const payload = await apiFetch("/v1/assessments?per_page=50&sort=-created_at");
    const items = payload.items || [];
    setAssessments(items);
    if (selectedAssessmentId && items.some((i) => i.id === selectedAssessmentId)) return;
    if (items.length) setSelectedAssessmentId(items[0].id);
  }

  async function loadFindings(assessmentId) {
    if (!assessmentId) return;
    const payload = await apiFetch(`/v1/assessments/${assessmentId}/findings?per_page=200&sort=severity`);
    const items = payload.items || [];
    setFindings(items);
    setSelectedFinding(null);
    setFindingPage(1);
  }

  async function createAssessment(event) {
    event.preventDefault();
    try {
      const payload =
        mode === "lightweight"
          ? { mode, repo_url: repoUrl.trim() }
          : {
              mode,
              target_url: targetUrl.trim(),
              depth,
              agents: Array.from(selectedAgents),
            };

      if (mode === "lightweight" && !payload.repo_url) throw new Error("Repository URL is required.");
      if (mode === "robust" && !payload.target_url) throw new Error("Target URL is required.");

      const created = await apiFetch("/v1/assessments", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(`Assessment queued: ${created.id}`);
      await loadAssessments();
    } catch (error) {
      setStatus(`Create failed: ${error.message}`);
    }
  }

  async function analyzeSelectedFinding() {
    if (!selectedAssessmentId || !selectedFinding) {
      setStatus("Select an assessment and finding first.");
      return;
    }
    try {
      setStatus(`Analyzing finding ${selectedFinding.id}...`);
      const result = await apiFetch(
        `/v1/assessments/${selectedAssessmentId}/findings/${selectedFinding.id}/analyze`,
        { method: "POST", body: JSON.stringify({}) },
      );
      setSelectedFinding((prev) => ({
        ...(prev || {}),
        __analysis: result,
      }));
      setStatus(`Analysis complete (${result.analysis_source || "fallback"}).`);
    } catch (error) {
      setStatus(`Analyze failed: ${error.message}`);
    }
  }

  async function searchMemoryForSelectedFinding() {
    if (!selectedFinding) {
      setStatus("Select a finding first.");
      return;
    }
    const query = `${selectedFinding.title || ""} ${selectedFinding.description || ""}`.trim();
    if (!query) {
      setStatus("Selected finding has no searchable text.");
      return;
    }
    try {
      setStatus("Searching memory...");
      const qs = new URLSearchParams({ q: query, limit: "5" });
      if (selectedAssessmentId) qs.set("assessment_id", selectedAssessmentId);
      const result = await apiFetch(`/v1/memory/search?${qs.toString()}`);
      setSelectedFinding((prev) => ({
        ...(prev || {}),
        __memory: result,
      }));
      setStatus("Memory search complete.");
    } catch (error) {
      setStatus(`Memory search failed: ${error.message}`);
    }
  }

  function exportVisibleFindingsJson() {
    const data = pagedFindings;
    if (!data.length) {
      setStatus("No findings to export.");
      return;
    }
    downloadFile(
      `findings-${selectedAssessmentId || "none"}-page-${findingPage}.json`,
      JSON.stringify(data, null, 2),
      "application/json",
    );
    setStatus("JSON exported.");
  }

  function exportVisibleFindingsCsv() {
    const rows = pagedFindings;
    if (!rows.length) {
      setStatus("No findings to export.");
      return;
    }
    const headers = ["id", "severity", "category", "title", "agent", "created_at"];
    const lines = [headers.join(",")];
    rows.forEach((f) => {
      lines.push(
        [
          csvCell(f.id),
          csvCell(f.severity),
          csvCell(f.category),
          csvCell(f.title),
          csvCell(f.agent),
          csvCell(f.created_at),
        ].join(","),
      );
    });
    downloadFile(`findings-${selectedAssessmentId || "none"}-page-${findingPage}.csv`, `${lines.join("\n")}\n`, "text/csv");
    setStatus("CSV exported.");
  }

  useEffect(() => {
    loadAssessments().catch((error) => setStatus(`Initial load failed: ${error.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedAssessmentId) return;
    loadFindings(selectedAssessmentId).catch((error) => setStatus(`Findings load failed: ${error.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAssessmentId]);

  useEffect(() => {
    if (!autoPoll) return undefined;
    const timer = window.setInterval(() => {
      loadAssessments().catch(() => {});
      if (selectedAssessmentId) loadFindings(selectedAssessmentId).catch(() => {});
    }, 5000);
    return () => window.clearInterval(timer);
  }, [autoPoll, selectedAssessmentId]);

  const stats = useMemo(() => {
    return {
      total: assessments.length,
      active: assessments.filter((a) => ACTIVE_STATUSES.has(a.status)).length,
      complete: assessments.filter((a) => a.status === "complete").length,
      failed: assessments.filter((a) => a.status === "failed").length,
    };
  }, [assessments]);

  const pagedAssessments = useMemo(() => {
    const totalPages = Math.max(1, Math.ceil(assessments.length / asmPerPage));
    const safePage = Math.min(asmPage, totalPages);
    const start = (safePage - 1) * asmPerPage;
    return {
      rows: assessments.slice(start, start + asmPerPage),
      totalPages,
      page: safePage,
    };
  }, [assessments, asmPage]);

  const filteredFindings = useMemo(() => {
    return findings
      .filter((f) => {
        if (severity && f.severity !== severity) return false;
        if (search) {
          const hay = `${f.title || ""} ${f.description || ""}`.toLowerCase();
          if (!hay.includes(search.toLowerCase())) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const rankA = SEVERITY_ORDER[a.severity] ?? 99;
        const rankB = SEVERITY_ORDER[b.severity] ?? 99;
        if (rankA !== rankB) return rankA - rankB;
        return new Date(b.created_at || 0) - new Date(a.created_at || 0);
      });
  }, [findings, search, severity]);

  const pagedFindings = useMemo(() => {
    const totalPages = Math.max(1, Math.ceil(filteredFindings.length / findingPerPage));
    const safePage = Math.min(findingPage, totalPages);
    const start = (safePage - 1) * findingPerPage;
    return filteredFindings.slice(start, start + findingPerPage);
  }, [filteredFindings, findingPage]);

  const findingPages = Math.max(1, Math.ceil(filteredFindings.length / findingPerPage));

  return html`
    <div className="shell">
      <header className="top">
        <div>
          <p className="eyebrow">Security Orchestration</p>
          <h1>VibeCheck Control Center</h1>
          <p className="muted">React dashboard (production view).</p>
        </div>
        <div className="top-links">
          <a className="link-btn" href="./docs.html">API Docs</a>
          <a className="link-btn" href="/docs">FastAPI Swagger</a>
        </div>
      </header>

      <main className="layout">
        <section className="card">
          <h2>Create Assessment</h2>
          <form onSubmit=${createAssessment}>
            <label>API Base URL</label>
            <input value=${apiBase} onInput=${(e) => setApiBase(e.target.value)} placeholder="https://vibecheck.aedify.ai" />

            <label>Scan Mode</label>
            <select value=${mode} onChange=${(e) => setMode(e.target.value)}>
              <option value="lightweight">Lightweight</option>
              <option value="robust">Robust</option>
            </select>

            ${mode === "lightweight"
              ? html`
                  <label>Repository URL</label>
                  <input
                    type="url"
                    placeholder="https://github.com/org/repo"
                    value=${repoUrl}
                    onInput=${(e) => setRepoUrl(e.target.value)}
                  />
                `
              : html`
                  <label>Target URL</label>
                  <input
                    type="url"
                    placeholder="http://localhost:3000"
                    value=${targetUrl}
                    onInput=${(e) => setTargetUrl(e.target.value)}
                  />

                  <label>Depth</label>
                  <select value=${depth} onChange=${(e) => setDepth(e.target.value)}>
                    <option value="quick">Quick</option>
                    <option value="standard">Standard</option>
                    <option value="deep">Deep</option>
                  </select>

                  <label>Agents</label>
                  <div className="checks">
                    ${AGENTS.map(
                      (agent) => html`
                        <label key=${agent}>
                          <input
                            type="checkbox"
                            checked=${selectedAgents.has(agent)}
                            onChange=${() => {
                              const next = new Set(selectedAgents);
                              if (next.has(agent)) next.delete(agent);
                              else next.add(agent);
                              setSelectedAgents(next);
                            }}
                          />
                          ${agent}
                        </label>
                      `,
                    )}
                  </div>
                `}
            <button type="submit">Start Assessment</button>
          </form>
          <p className="status">${status}</p>
        </section>

        <section className="stack">
          <section className="card">
            <div className="row">
              <h2>Assessment Snapshot</h2>
              <div className="actions">
                <button className="secondary" onClick=${() => loadAssessments().catch((e) => setStatus(e.message))}>
                  Refresh
                </button>
                <button className="secondary" onClick=${() => setAutoPoll((v) => !v)}>
                  Auto Poll: ${autoPoll ? "On" : "Off"}
                </button>
              </div>
            </div>
            <div className="stats">
              <div className="stat"><p>Total Assessments</p><strong>${stats.total}</strong></div>
              <div className="stat"><p>Queued / Running</p><strong>${stats.active}</strong></div>
              <div className="stat"><p>Completed</p><strong>${stats.complete}</strong></div>
              <div className="stat"><p>Failed</p><strong>${stats.failed}</strong></div>
            </div>
          </section>

          <section className="card">
            <div className="row">
              <h2>Assessments</h2>
              <p className="muted">${selectedAssessmentId ? `Selected: ${selectedAssessmentId}` : "Select an assessment."}</p>
            </div>
            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Mode</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Findings</th>
                  </tr>
                </thead>
                <tbody>
                  ${pagedAssessments.rows.map(
                    (a) => html`
                      <tr key=${a.id} onClick=${() => setSelectedAssessmentId(a.id)}>
                        <td>${a.id}</td>
                        <td>${a.mode}</td>
                        <td><span className=${`badge ${badgeClass("st", a.status)}`}>${a.status || "-"}</span></td>
                        <td>${formatDate(a.created_at)}</td>
                        <td>${a.finding_counts?.total ?? 0}</td>
                      </tr>
                    `,
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button className="secondary" disabled=${pagedAssessments.page <= 1} onClick=${() => setAsmPage((p) => Math.max(1, p - 1))}>
                Previous
              </button>
              <span>Page ${pagedAssessments.page} / ${pagedAssessments.totalPages}</span>
              <button
                className="secondary"
                disabled=${pagedAssessments.page >= pagedAssessments.totalPages}
                onClick=${() => setAsmPage((p) => Math.min(pagedAssessments.totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          </section>

          <section className="card">
            <div className="row">
              <h2>Findings</h2>
              <div className="actions">
                <button className="secondary" onClick=${exportVisibleFindingsCsv}>Export CSV</button>
                <button className="secondary" onClick=${exportVisibleFindingsJson}>Export JSON</button>
                <button className="secondary" onClick=${analyzeSelectedFinding}>Analyze Finding</button>
                <button className="secondary" onClick=${searchMemoryForSelectedFinding}>Find Similar</button>
              </div>
            </div>

            <div className="filters">
              <input placeholder="Search title or description" value=${search} onInput=${(e) => setSearch(e.target.value)} />
              <select value=${severity} onChange=${(e) => setSeverity(e.target.value)}>
                <option value="">All Severities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
                <option value="info">Info</option>
              </select>
            </div>

            <div className="table">
              <table>
                <thead>
                  <tr>
                    <th>Severity</th>
                    <th>Category</th>
                    <th>Title</th>
                    <th>Agent</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  ${pagedFindings.map(
                    (f) => html`
                      <tr key=${f.id} onClick=${() => setSelectedFinding(f)}>
                        <td><span className=${`badge ${badgeClass("sev", f.severity)}`}>${f.severity || "-"}</span></td>
                        <td>${f.category || "-"}</td>
                        <td>${f.title || "-"}</td>
                        <td>${f.agent || "-"}</td>
                        <td>${formatDate(f.created_at)}</td>
                      </tr>
                    `,
                  )}
                </tbody>
              </table>
            </div>
            <div className="pager">
              <button className="secondary" disabled=${findingPage <= 1} onClick=${() => setFindingPage((p) => Math.max(1, p - 1))}>
                Previous
              </button>
              <span>Page ${Math.min(findingPage, findingPages)} / ${findingPages}</span>
              <button className="secondary" disabled=${findingPage >= findingPages} onClick=${() => setFindingPage((p) => Math.min(findingPages, p + 1))}>
                Next
              </button>
            </div>

            <div className="detail">
              ${selectedFinding
                ? JSON.stringify(
                    {
                      ...selectedFinding,
                      analysis: selectedFinding.__analysis || undefined,
                      memory: selectedFinding.__memory || undefined,
                    },
                    null,
                    2,
                  )
                : "Select a finding to inspect details."}
            </div>
          </section>
        </section>
      </main>
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
