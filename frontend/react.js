import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18.3.1";
import { createRoot } from "https://esm.sh/react-dom@18.3.1/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);
const AGENTS = ["recon", "auth", "injection", "config"];

function formatDate(ts) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function safeJson(value) {
  return JSON.stringify(value, null, 2);
}

function App() {
  const [apiBase, setApiBase] = useState("http://localhost:8000");
  const [mode, setMode] = useState("lightweight");
  const [repoUrl, setRepoUrl] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [depth, setDepth] = useState("standard");
  const [status, setStatus] = useState("");
  const [autoPoll, setAutoPoll] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState(new Set(AGENTS));
  const [assessments, setAssessments] = useState([]);
  const [selectedAssessmentId, setSelectedAssessmentId] = useState(null);
  const [findings, setFindings] = useState([]);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [selectedFinding, setSelectedFinding] = useState(null);

  async function apiFetch(path, options = {}) {
    const response = await fetch(`${apiBase.replace(/\/$/, "")}${path}`, {
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
    if (!selectedAssessmentId && items.length) setSelectedAssessmentId(items[0].id);
  }

  async function loadFindings(id) {
    if (!id) return;
    const payload = await apiFetch(`/v1/assessments/${id}/findings?per_page=200&sort=severity`);
    const items = payload.items || [];
    setFindings(items);
    setSelectedFinding(null);
  }

  useEffect(() => {
    loadAssessments().catch((e) => setStatus(`Load failed: ${e.message}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedAssessmentId) return;
    loadFindings(selectedAssessmentId).catch((e) => setStatus(`Findings failed: ${e.message}`));
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
    const total = assessments.length;
    const active = assessments.filter((a) => ["queued", "cloning", "analyzing", "scanning"].includes(a.status)).length;
    const complete = assessments.filter((a) => a.status === "complete").length;
    const failed = assessments.filter((a) => a.status === "failed").length;
    return { total, active, complete, failed };
  }, [assessments]);

  const filteredFindings = useMemo(() => {
    return findings.filter((f) => {
      if (severity && f.severity !== severity) return false;
      if (search) {
        const text = `${f.title || ""} ${f.description || ""}`.toLowerCase();
        if (!text.includes(search.toLowerCase())) return false;
      }
      return true;
    });
  }, [findings, search, severity]);

  async function createAssessment(event) {
    event.preventDefault();
    try {
      const payload =
        mode === "lightweight"
          ? { mode, repo_url: repoUrl.trim() }
          : { mode, target_url: targetUrl.trim(), depth, agents: Array.from(selectedAgents) };
      if (mode === "lightweight" && !payload.repo_url) throw new Error("Repository URL required");
      if (mode === "robust" && !payload.target_url) throw new Error("Target URL required");

      const created = await apiFetch("/v1/assessments", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      setStatus(`Queued: ${created.id}`);
      await loadAssessments();
    } catch (e) {
      setStatus(`Create failed: ${e.message}`);
    }
  }

  return html`
    <div className="shell">
      <header className="top">
        <div>
          <p className="eyebrow">Security Orchestration</p>
          <h1>VibeCheck React Dashboard</h1>
          <p className="muted">Alternative UI using React, without changing backend APIs.</p>
        </div>
        <div className="top-links">
          <a className="link-btn" href="./index.html">Classic Dashboard</a>
          <a className="link-btn" href="./docs.html">API Docs</a>
        </div>
      </header>

      <main className="layout">
        <section className="card">
          <h2>Create Assessment</h2>
          <form onSubmit=${createAssessment}>
            <label>API Base URL</label>
            <input value=${apiBase} onInput=${(e) => setApiBase(e.target.value)} />

            <label>Mode</label>
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
                      (a) => html`
                        <label key=${a}>
                          <input
                            type="checkbox"
                            checked=${selectedAgents.has(a)}
                            onChange=${() => {
                              const next = new Set(selectedAgents);
                              if (next.has(a)) next.delete(a);
                              else next.add(a);
                              setSelectedAgents(next);
                            }}
                          />
                          ${a}
                        </label>
                      `,
                    )}
                  </div>
                `}

            <button type="submit">Start Assessment</button>
          </form>
          <p className="status">${status || "Ready."}</p>
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
              <div className="stat"><p>Total</p><strong>${stats.total}</strong></div>
              <div className="stat"><p>Active</p><strong>${stats.active}</strong></div>
              <div className="stat"><p>Completed</p><strong>${stats.complete}</strong></div>
              <div className="stat"><p>Failed</p><strong>${stats.failed}</strong></div>
            </div>
          </section>

          <section className="card">
            <h2>Assessments</h2>
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
                  ${assessments.map(
                    (a) => html`
                      <tr key=${a.id} onClick=${() => setSelectedAssessmentId(a.id)}>
                        <td>${a.id}</td>
                        <td>${a.mode}</td>
                        <td><span className=${`badge st-${a.status || "unknown"}`}>${a.status || "-"}</span></td>
                        <td>${formatDate(a.created_at)}</td>
                        <td>${a.finding_counts?.total ?? 0}</td>
                      </tr>
                    `,
                  )}
                </tbody>
              </table>
            </div>
          </section>

          <section className="card">
            <h2>Findings</h2>
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
                  </tr>
                </thead>
                <tbody>
                  ${filteredFindings.map(
                    (f) => html`
                      <tr key=${f.id} onClick=${() => setSelectedFinding(f)}>
                        <td><span className=${`badge sev-${f.severity || "info"}`}>${f.severity || "-"}</span></td>
                        <td>${f.category || "-"}</td>
                        <td>${f.title || "-"}</td>
                        <td>${f.agent || "-"}</td>
                      </tr>
                    `,
                  )}
                </tbody>
              </table>
            </div>
            <div className="detail">${selectedFinding ? safeJson(selectedFinding) : "Select a finding to inspect details."}</div>
          </section>
        </section>
      </main>
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
