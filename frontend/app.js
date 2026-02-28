const state = {
  assessments: [],
  assessmentsPage: 1,
  assessmentsPerPage: 15,
  assessmentsTotalPages: 1,
  selectedAssessmentId: null,
  findings: [],
  currentPage: 1,
  perPage: 15,
  totalPages: 1,
  autoPoll: false,
  pollTimer: null,
  assessmentWs: null,
  wsAssessmentId: null,
  statusPollTimer: null,
  statusPollAssessmentId: null,
};

const els = {
  apiBase: document.getElementById("apiBase"),
  createForm: document.getElementById("createForm"),
  scanMode: document.getElementById("scanMode"),
  lightweightFields: document.getElementById("lightweightFields"),
  robustFields: document.getElementById("robustFields"),
  repoUrl: document.getElementById("repoUrl"),
  targetUrl: document.getElementById("targetUrl"),
  tunnelSessionId: document.getElementById("tunnelSessionId"),
  tunnelSessionSelect: document.getElementById("tunnelSessionSelect"),
  loadTunnels: document.getElementById("loadTunnels"),
  depth: document.getElementById("depth"),
  idempotencyKey: document.getElementById("idempotencyKey"),
  createBtn: document.getElementById("createBtn"),
  createStatus: document.getElementById("createStatus"),
  refreshAssessments: document.getElementById("refreshAssessments"),
  autoPollToggle: document.getElementById("autoPollToggle"),
  assessmentsTable: document.getElementById("assessmentsTable"),
  asmPrevPage: document.getElementById("asmPrevPage"),
  asmNextPage: document.getElementById("asmNextPage"),
  asmPageInfo: document.getElementById("asmPageInfo"),
  findingsTable: document.getElementById("findingsTable"),
  exportCsv: document.getElementById("exportCsv"),
  exportJson: document.getElementById("exportJson"),
  selectedAssessmentLabel: document.getElementById("selectedAssessmentLabel"),
  analyzeFinding: document.getElementById("analyzeFinding"),
  searchMemory: document.getElementById("searchMemory"),
  findingDetail: document.getElementById("findingDetail"),
  statTotal: document.getElementById("statTotal"),
  statActive: document.getElementById("statActive"),
  statComplete: document.getElementById("statComplete"),
  statFailed: document.getElementById("statFailed"),
  severityFilter: document.getElementById("severityFilter"),
  categoryFilter: document.getElementById("categoryFilter"),
  agentFilter: document.getElementById("agentFilter"),
  sortBy: document.getElementById("sortBy"),
  searchInput: document.getElementById("searchInput"),
  prevPage: document.getElementById("prevPage"),
  nextPage: document.getElementById("nextPage"),
  pageInfo: document.getElementById("pageInfo"),
  severityChart: document.getElementById("severityChart"),
  trendChart: document.getElementById("trendChart"),
};

let selectedFindingId = null;

function getApiBase() {
  return els.apiBase.value.trim().replace(/\/$/, "");
}

function getWsBase() {
  const apiBase = getApiBase();
  if (apiBase.startsWith("https://")) return `wss://${apiBase.slice("https://".length)}`;
  if (apiBase.startsWith("http://")) return `ws://${apiBase.slice("http://".length)}`;
  return apiBase.replace(/^http/, "ws");
}

async function apiFetch(path, options = {}) {
  const url = `${getApiBase()}${path}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body?.error?.message || JSON.stringify(body);
    } catch {
      // Keep default detail.
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

function formatDate(ts) {
  if (!ts) return "-";
  return new Date(ts).toLocaleString();
}

function badge(value, prefix) {
  const cls = (value || "unknown").toLowerCase();
  return `<span class="badge ${prefix}-${cls}">${value || "-"}</span>`;
}

function renderStats() {
  const total = state.assessments.length;
  const active = state.assessments.filter((a) => ["queued", "cloning", "analyzing", "scanning"].includes(a.status)).length;
  const complete = state.assessments.filter((a) => a.status === "complete").length;
  const failed = state.assessments.filter((a) => a.status === "failed").length;

  els.statTotal.textContent = String(total);
  els.statActive.textContent = String(active);
  els.statComplete.textContent = String(complete);
  els.statFailed.textContent = String(failed);
}

function renderAssessments() {
  if (!state.assessments.length) {
    els.assessmentsTable.innerHTML = `<tr><td colspan="5">No assessments yet.</td></tr>`;
    els.asmPageInfo.textContent = "Page 1 / 1";
    els.asmPrevPage.disabled = true;
    els.asmNextPage.disabled = true;
    renderStats();
    return;
  }

  state.assessmentsTotalPages = Math.max(1, Math.ceil(state.assessments.length / state.assessmentsPerPage));
  state.assessmentsPage = Math.min(state.assessmentsPage, state.assessmentsTotalPages);
  const start = (state.assessmentsPage - 1) * state.assessmentsPerPage;
  const pageItems = state.assessments.slice(start, start + state.assessmentsPerPage);

  els.assessmentsTable.innerHTML = pageItems
    .map((a) => {
      const isSelected = state.selectedAssessmentId === a.id ? " style=\"background: rgba(14, 95, 155, 0.1);\"" : "";
      return `
        <tr class="clickable" data-assessment-id="${a.id}"${isSelected}>
          <td>${a.id}</td>
          <td>${a.mode}</td>
          <td>${badge(a.status, "badge")}</td>
          <td>${formatDate(a.created_at)}</td>
          <td>${a.finding_counts?.total ?? 0}</td>
        </tr>
      `;
    })
    .join("");

  els.asmPageInfo.textContent = `Page ${state.assessmentsPage} / ${state.assessmentsTotalPages}`;
  els.asmPrevPage.disabled = state.assessmentsPage <= 1;
  els.asmNextPage.disabled = state.assessmentsPage >= state.assessmentsTotalPages;
  renderStats();
}

function populateFilterOptions() {
  const categories = new Set();
  const agents = new Set();

  state.findings.forEach((f) => {
    if (f.category) categories.add(f.category);
    if (f.agent) agents.add(f.agent);
  });

  els.categoryFilter.innerHTML = `<option value="">All Categories</option>${[...categories]
    .sort()
    .map((c) => `<option value="${c}">${c}</option>`)
    .join("")}`;

  els.agentFilter.innerHTML = `<option value="">All Agents</option>${[...agents]
    .sort()
    .map((a) => `<option value="${a}">${a}</option>`)
    .join("")}`;
}

function findingLocationText(location) {
  if (!location) return "-";
  if (location.file) return `${location.file}${location.line ? `:${location.line}` : ""}`;
  if (location.url) return location.url;
  if (location.type) return location.type;
  return JSON.stringify(location);
}

function getFilteredFindings() {
  const search = els.searchInput.value.trim().toLowerCase();
  const severity = els.severityFilter.value;
  const category = els.categoryFilter.value;
  const agent = els.agentFilter.value;

  return state.findings.filter((f) => {
    if (severity && f.severity !== severity) return false;
    if (category && f.category !== category) return false;
    if (agent && f.agent !== agent) return false;
    if (search) {
      const haystack = `${f.title || ""} ${f.description || ""}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

function sortFindings(findings) {
  const sortBy = els.sortBy.value;
  if (sortBy === "created_at") {
    return [...findings].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
  }

  const severityRank = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
  return [...findings].sort((a, b) => {
    const sa = severityRank[a.severity] ?? 99;
    const sb = severityRank[b.severity] ?? 99;
    if (sa !== sb) return sa - sb;
    return new Date(b.created_at) - new Date(a.created_at);
  });
}

function getVisibleFindings() {
  return sortFindings(getFilteredFindings());
}

function triggerDownload(filename, content, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvCell(value) {
  if (value == null) return "";
  const text = String(value).replace(/"/g, "\"\"");
  return `"${text}"`;
}

function exportFindingsCsv() {
  if (!state.selectedAssessmentId) {
    els.createStatus.textContent = "Select an assessment before exporting.";
    return;
  }
  const rows = getVisibleFindings();
  if (!rows.length) {
    els.createStatus.textContent = "No findings available for current filters.";
    return;
  }

  const headers = ["id", "severity", "category", "title", "agent", "location", "created_at", "description", "remediation"];
  const lines = [headers.join(",")];
  rows.forEach((f) => {
    const location = findingLocationText(f.location);
    const line = [
      csvCell(f.id),
      csvCell(f.severity),
      csvCell(f.category),
      csvCell(f.title),
      csvCell(f.agent),
      csvCell(location),
      csvCell(f.created_at),
      csvCell(f.description),
      csvCell(f.remediation),
    ].join(",");
    lines.push(line);
  });

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  triggerDownload(`findings-${state.selectedAssessmentId}-${stamp}.csv`, `${lines.join("\n")}\n`, "text/csv;charset=utf-8");
}

function exportFindingsJson() {
  if (!state.selectedAssessmentId) {
    els.createStatus.textContent = "Select an assessment before exporting.";
    return;
  }
  const rows = getVisibleFindings();
  if (!rows.length) {
    els.createStatus.textContent = "No findings available for current filters.";
    return;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  triggerDownload(
    `findings-${state.selectedAssessmentId}-${stamp}.json`,
    `${JSON.stringify(rows, null, 2)}\n`,
    "application/json;charset=utf-8",
  );
}

function drawSeverityChart() {
  const canvas = els.severityChart;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width;
  canvas.height = height;

  ctx.clearRect(0, 0, width, height);
  const levels = ["critical", "high", "medium", "low", "info"];
  const colors = {
    critical: "#c0392b",
    high: "#a8382e",
    medium: "#cc7a00",
    low: "#3f5870",
    info: "#5d6882",
  };
  const counts = levels.map((level) => state.findings.filter((f) => f.severity === level).length);
  const max = Math.max(1, ...counts);

  const padding = { top: 16, right: 10, bottom: 34, left: 30 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;
  const slot = chartW / levels.length;
  const barW = Math.min(58, slot * 0.6);

  ctx.strokeStyle = "#d9e3f0";
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, padding.top + chartH);
  ctx.lineTo(padding.left + chartW, padding.top + chartH);
  ctx.stroke();

  levels.forEach((level, idx) => {
    const value = counts[idx];
    const x = padding.left + idx * slot + (slot - barW) / 2;
    const h = (value / max) * chartH;
    const y = padding.top + chartH - h;

    ctx.fillStyle = colors[level];
    ctx.fillRect(x, y, barW, h);

    ctx.fillStyle = "#465267";
    ctx.font = "12px Plus Jakarta Sans";
    ctx.textAlign = "center";
    ctx.fillText(level, x + barW / 2, padding.top + chartH + 16);
    ctx.fillText(String(value), x + barW / 2, y - 6);
  });
}

function drawTrendChart() {
  const canvas = els.trendChart;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width;
  canvas.height = height;
  ctx.clearRect(0, 0, width, height);

  const assessments = [...state.assessments]
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
    .slice(-20);

  const values = assessments.map((a) => a.finding_counts?.total ?? 0);
  const max = Math.max(1, ...values);
  const padding = { top: 16, right: 12, bottom: 34, left: 30 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  ctx.strokeStyle = "#d9e3f0";
  ctx.beginPath();
  ctx.moveTo(padding.left, padding.top);
  ctx.lineTo(padding.left, padding.top + chartH);
  ctx.lineTo(padding.left + chartW, padding.top + chartH);
  ctx.stroke();

  if (!assessments.length) {
    ctx.fillStyle = "#5d6882";
    ctx.font = "13px Plus Jakarta Sans";
    ctx.fillText("No assessment data available.", padding.left + 6, padding.top + chartH / 2);
    return;
  }

  const xStep = assessments.length > 1 ? chartW / (assessments.length - 1) : 0;
  const points = values.map((value, i) => ({
    x: padding.left + i * xStep,
    y: padding.top + chartH - (value / max) * chartH,
    value,
  }));

  ctx.strokeStyle = "#0e5f9b";
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((p, i) => {
    if (i === 0) ctx.moveTo(p.x, p.y);
    else ctx.lineTo(p.x, p.y);
  });
  ctx.stroke();

  points.forEach((p, i) => {
    ctx.fillStyle = "#0f8f7a";
    ctx.beginPath();
    ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
    ctx.fill();

    if (i % Math.max(1, Math.floor(points.length / 6)) === 0 || i === points.length - 1) {
      ctx.fillStyle = "#465267";
      ctx.font = "11px Plus Jakarta Sans";
      ctx.textAlign = "center";
      ctx.fillText(String(p.value), p.x, p.y - 8);
    }
  });

  const firstTs = formatDate(assessments[0].created_at);
  const lastTs = formatDate(assessments[assessments.length - 1].created_at);
  ctx.fillStyle = "#5d6882";
  ctx.font = "11px Plus Jakarta Sans";
  ctx.textAlign = "left";
  ctx.fillText(firstTs, padding.left, height - 8);
  ctx.textAlign = "right";
  ctx.fillText(lastTs, width - padding.right, height - 8);
}

function renderCharts() {
  drawSeverityChart();
  drawTrendChart();
}

function renderFindings() {
  if (!state.selectedAssessmentId) {
    els.findingsTable.innerHTML = `<tr><td colspan="6">Choose an assessment first.</td></tr>`;
    els.pageInfo.textContent = "Page 1";
    els.prevPage.disabled = true;
    els.nextPage.disabled = true;
    renderCharts();
    return;
  }

  const filtered = getVisibleFindings();
  state.totalPages = Math.max(1, Math.ceil(filtered.length / state.perPage));
  state.currentPage = Math.min(state.currentPage, state.totalPages);

  const start = (state.currentPage - 1) * state.perPage;
  const pageItems = filtered.slice(start, start + state.perPage);

  if (!pageItems.length) {
    els.findingsTable.innerHTML = `<tr><td colspan="6">No findings match current filters.</td></tr>`;
  } else {
    els.findingsTable.innerHTML = pageItems
      .map(
        (f) => `
          <tr class="clickable" data-finding-id="${f.id}">
            <td>${badge(f.severity, "badge")}</td>
            <td>${f.category || "-"}</td>
            <td>${f.title || "-"}</td>
            <td>${f.agent || "-"}</td>
            <td>${findingLocationText(f.location)}</td>
            <td>${formatDate(f.created_at)}</td>
          </tr>
        `,
      )
      .join("");
  }

  els.pageInfo.textContent = `Page ${state.currentPage} / ${state.totalPages}`;
  els.prevPage.disabled = state.currentPage <= 1;
  els.nextPage.disabled = state.currentPage >= state.totalPages;
  renderCharts();
}

async function loadAssessments() {
  const payload = await apiFetch("/v1/assessments?per_page=50&sort=-created_at");
  state.assessments = payload.data || [];

  if (!state.selectedAssessmentId && state.assessments.length) {
    state.selectedAssessmentId = state.assessments[0].id;
    await loadFindings(state.selectedAssessmentId);
  }
  if (state.assessmentsPage < 1) {
    state.assessmentsPage = 1;
  }

  renderAssessments();
  renderCharts();

  const selected = state.assessments.find((a) => a.id === state.selectedAssessmentId);
  if (selected && ["queued", "cloning", "analyzing", "scanning"].includes(selected.status)) {
    subscribeAssessmentStatus(selected.id);
  }
}

function setCreateModeUI() {
  const mode = els.scanMode.value;
  const isLightweight = mode === "lightweight";

  els.lightweightFields.classList.toggle("hidden", !isLightweight);
  els.robustFields.classList.toggle("hidden", isLightweight);

  if (isLightweight) {
    els.repoUrl.required = true;
    els.targetUrl.required = false;
  } else {
    els.repoUrl.required = false;
    els.targetUrl.required = true;
  }
}

async function loadTunnelSessions() {
  try {
    const payload = await apiFetch("/v1/tunnel/sessions");
    const sessions = payload.data || [];
    els.tunnelSessionSelect.innerHTML = [
      `<option value="">Select active tunnel session (optional)</option>`,
      ...sessions
        .filter((s) => s.status === "connected")
        .map((s) => `<option value="${s.id}">${s.id} (port ${s.target_port})</option>`),
    ].join("");
  } catch (e) {
    els.createStatus.textContent = `Could not load tunnel sessions: ${e.message}`;
  }
}

async function loadFindings(assessmentId) {
  const payload = await apiFetch(`/v1/assessments/${assessmentId}/findings?per_page=200&sort=severity`);
  state.findings = payload.data || [];
  state.currentPage = 1;
  els.selectedAssessmentLabel.textContent = `Assessment: ${assessmentId}`;
  populateFilterOptions();
  renderFindings();
}

async function createAssessment(event) {
  event.preventDefault();
  els.createBtn.disabled = true;
  els.createStatus.textContent = "Submitting assessment...";

  try {
    const mode = els.scanMode.value;
    const body = { mode };

    if (mode === "lightweight") {
      const repoUrl = els.repoUrl.value.trim();
      if (!repoUrl) {
        throw new Error("Repository URL is required for lightweight mode.");
      }
      body.repo_url = repoUrl;
    } else {
      const targetUrl = els.targetUrl.value.trim();
      if (!targetUrl) {
        throw new Error("Target URL is required for robust mode.");
      }
      body.target_url = targetUrl;

      const selectedAgents = [...document.querySelectorAll(".agent-check:checked")].map((n) => n.value);
      if (!selectedAgents.length) {
        throw new Error("Select at least one robust agent.");
      }
      body.agents = selectedAgents;
      body.depth = els.depth.value;

      const tunnelSession = els.tunnelSessionId.value.trim() || els.tunnelSessionSelect.value.trim();
      if (tunnelSession) {
        body.tunnel_session_id = tunnelSession;
      }
    }

    const key = els.idempotencyKey.value.trim();
    if (key) body.idempotency_key = key;

    const created = await apiFetch("/v1/assessments", {
      method: "POST",
      body: JSON.stringify(body),
    });

    els.createStatus.textContent = `Assessment queued: ${created.id}`;
    state.selectedAssessmentId = created.id;
    subscribeAssessmentStatus(created.id);

    await loadAssessments();
  } catch (error) {
    els.createStatus.textContent = `Failed: ${error.message}`;
  } finally {
    els.createBtn.disabled = false;
  }
}

function applyAssessmentUpdate(update) {
  const idx = state.assessments.findIndex((a) => a.id === update.id);
  if (idx >= 0) {
    state.assessments[idx] = { ...state.assessments[idx], ...update };
  }
  renderAssessments();
  renderCharts();
}

function stopStatusPoll() {
  if (state.statusPollTimer) {
    window.clearInterval(state.statusPollTimer);
    state.statusPollTimer = null;
    state.statusPollAssessmentId = null;
  }
}

function startStatusPoll(assessmentId) {
  if (!assessmentId) return;
  if (state.statusPollTimer && state.statusPollAssessmentId === assessmentId) return;
  stopStatusPoll();
  state.statusPollAssessmentId = assessmentId;
  state.statusPollTimer = window.setInterval(async () => {
    try {
      const assessment = await apiFetch(`/v1/assessments/${assessmentId}`);
      applyAssessmentUpdate(assessment);
      if (assessment.status === "complete" || assessment.status === "failed") {
        stopStatusPoll();
        if (state.selectedAssessmentId === assessmentId) {
          await loadFindings(assessmentId);
        }
      }
    } catch {
      // Ignore transient errors in fallback poll.
    }
  }, 3000);
}

function closeAssessmentSocket() {
  if (state.assessmentWs) {
    state.assessmentWs.close();
    state.assessmentWs = null;
    state.wsAssessmentId = null;
  }
  stopStatusPoll();
}

function subscribeAssessmentStatus(assessmentId) {
  if (!assessmentId) return;
  if (
    state.assessmentWs &&
    state.wsAssessmentId === assessmentId &&
    state.assessmentWs.readyState <= WebSocket.OPEN
  ) {
    return;
  }

  closeAssessmentSocket();
  startStatusPoll(assessmentId);
  const ws = new WebSocket(`${getWsBase()}/v1/assessments/${assessmentId}/ws`);
  state.assessmentWs = ws;
  state.wsAssessmentId = assessmentId;

  ws.onmessage = async (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "assessment_update" || msg.type === "assessment_terminal") {
        applyAssessmentUpdate(msg.data);
        if (state.selectedAssessmentId === msg.data.id) {
          els.createStatus.textContent = `Assessment ${msg.data.id} status: ${msg.data.status}`;
        }
      }

      if (msg.type === "assessment_terminal") {
        stopStatusPoll();
        if (state.selectedAssessmentId === msg.data.id) {
          await loadFindings(msg.data.id);
          await loadAssessments();
        }
        closeAssessmentSocket();
      }
    } catch {
      // Ignore malformed WS messages.
    }
  };

  ws.onerror = () => {
    // Keep silent; polling/refresh still works as fallback.
  };

  ws.onclose = () => {
    if (state.wsAssessmentId === assessmentId) {
      state.assessmentWs = null;
      state.wsAssessmentId = null;
    }
  };
}

function setupEvents() {
  els.createForm.addEventListener("submit", createAssessment);
  els.scanMode.addEventListener("change", setCreateModeUI);
  els.loadTunnels.addEventListener("click", loadTunnelSessions);
  els.tunnelSessionSelect.addEventListener("change", () => {
    if (els.tunnelSessionSelect.value) {
      els.tunnelSessionId.value = els.tunnelSessionSelect.value;
    }
  });

  els.refreshAssessments.addEventListener("click", async () => {
    try {
      await loadAssessments();
    } catch (e) {
      els.createStatus.textContent = `Refresh failed: ${e.message}`;
    }
  });

  els.asmPrevPage.addEventListener("click", () => {
    if (state.assessmentsPage > 1) {
      state.assessmentsPage -= 1;
      renderAssessments();
    }
  });

  els.asmNextPage.addEventListener("click", () => {
    if (state.assessmentsPage < state.assessmentsTotalPages) {
      state.assessmentsPage += 1;
      renderAssessments();
    }
  });

  els.exportCsv.addEventListener("click", exportFindingsCsv);
  els.exportJson.addEventListener("click", exportFindingsJson);

  els.autoPollToggle.addEventListener("click", () => {
    state.autoPoll = !state.autoPoll;
    els.autoPollToggle.textContent = `Auto Poll: ${state.autoPoll ? "On" : "Off"}`;

    if (state.autoPoll) {
      state.pollTimer = window.setInterval(async () => {
        try {
          await loadAssessments();
          if (state.selectedAssessmentId) {
            await loadFindings(state.selectedAssessmentId);
          }
        } catch {
          // Ignore transient errors during poll.
        }
      }, 5000);
    } else if (state.pollTimer) {
      window.clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
  });

  els.assessmentsTable.addEventListener("click", async (event) => {
    const row = event.target.closest("tr[data-assessment-id]");
    if (!row) return;

    const id = row.getAttribute("data-assessment-id");
    state.selectedAssessmentId = id;
    subscribeAssessmentStatus(id);

    try {
      await loadFindings(id);
      renderAssessments();
    } catch (e) {
      els.createStatus.textContent = `Could not load findings: ${e.message}`;
    }
  });

  els.findingsTable.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-finding-id]");
    if (!row) return;

    const finding = state.findings.find((f) => f.id === row.getAttribute("data-finding-id"));
    if (!finding) return;

    selectedFindingId = finding.id;
    const location = finding.location ? findingLocationText(finding.location) : "N/A";
    const evidence = finding.evidence ? "Available" : "Not available";
    els.findingDetail.textContent = [
      "=== Finding ===",
      `ID: ${finding.id}`,
      `Severity: ${finding.severity}`,
      `Category: ${finding.category}`,
      `Title: ${finding.title}`,
      `Agent: ${finding.agent || "N/A"}`,
      `Location: ${location}`,
      `Created: ${formatDate(finding.created_at)}`,
      "",
      "=== Description ===",
      finding.description || "N/A",
      "",
      "=== Remediation ===",
      finding.remediation || "N/A",
      "",
      `Evidence: ${evidence}`,
    ].join("\n");
  });

  els.searchMemory.addEventListener("click", async () => {
    if (!selectedFindingId) {
      els.createStatus.textContent = "Select a finding first, then run memory search.";
      return;
    }
    const finding = state.findings.find((f) => f.id === selectedFindingId);
    if (!finding) return;

    const query = `${finding.title || ""} ${finding.description || ""}`.trim();
    if (!query) {
      els.createStatus.textContent = "Selected finding has no searchable text.";
      return;
    }

    try {
      const qs = new URLSearchParams({
        q: query,
        limit: "5",
      });
      if (state.selectedAssessmentId) {
        qs.set("assessment_id", state.selectedAssessmentId);
      }
      const payload = await apiFetch(`/v1/memory/search?${qs.toString()}`);
      const summary = {
        selected_finding: finding.id,
        memory_enabled: payload.enabled,
        similar_results_count: (payload.results || []).length,
        results: payload.results || [],
      };
      els.findingDetail.textContent = `${JSON.stringify(finding, null, 2)}\n\n--- Supermemory Similar Results ---\n${JSON.stringify(summary, null, 2)}`;
    } catch (e) {
      els.createStatus.textContent = `Memory search failed: ${e.message}`;
    }
  });

  els.analyzeFinding.addEventListener("click", async () => {
    if (!state.selectedAssessmentId || !selectedFindingId) {
      els.createStatus.textContent = "Select an assessment and finding first.";
      return;
    }
    const finding = state.findings.find((f) => f.id === selectedFindingId);
    if (!finding) return;

    els.createStatus.textContent = `Analyzing finding ${selectedFindingId}...`;
    try {
      const payload = await apiFetch(
        `/v1/assessments/${state.selectedAssessmentId}/findings/${selectedFindingId}/analyze`,
        {
          method: "POST",
          body: JSON.stringify({}),
        },
      );
      const actions = (payload.actions || []).map((a, i) => `${i + 1}. ${a}`).join("\n");
      const where = payload.where_to_fix
        ? Object.entries(payload.where_to_fix)
            .map(([k, v]) => `${k}: ${v ?? "N/A"}`)
            .join("\n")
        : "Not specified";
      const related = payload.memory_similar_results_count ?? 0;
      const source = payload.analysis_source || "fallback";
      const relatedList = (payload.memory_similar_results || [])
        .slice(0, 5)
        .map((r, i) => {
          const title = r?.metadata?.title || r?.title || r?.customId || "similar finding";
          const sev = r?.metadata?.severity ? ` [${r.metadata.severity}]` : "";
          return `${i + 1}. ${title}${sev}`;
        })
        .join("\n");

      els.findingDetail.textContent = [
        "=== Analysis Summary ===",
        payload.summary || "N/A",
        "",
        "=== Impact ===",
        payload.impact || "N/A",
        "",
        "=== Possible Root Cause ===",
        payload.possible_root_cause || "N/A",
        "",
        `=== Guidance (${payload.mode || "unknown"} mode) ===`,
        payload.mode_guidance || "N/A",
        "",
        "=== Where To Fix ===",
        where,
        "",
        "=== Action Plan ===",
        actions || "1. Apply remediation and re-test",
        "",
        "=== Context ===",
        `Analysis source: ${source}`,
        `Similar historical findings: ${related}`,
        relatedList ? `Top similar:\n${relatedList}` : "Top similar: none",
        payload.error ? `Analyzer note: ${payload.error}` : "",
      ].filter(Boolean).join("\n");
      els.createStatus.textContent = `Analysis complete (${payload.analysis_source}).`;
    } catch (e) {
      els.createStatus.textContent = `Analyze failed: ${e.message}`;
    }
  });

  [els.searchInput, els.severityFilter, els.categoryFilter, els.agentFilter, els.sortBy].forEach((el) => {
    el.addEventListener("input", () => {
      state.currentPage = 1;
      renderFindings();
    });
    el.addEventListener("change", () => {
      state.currentPage = 1;
      renderFindings();
    });
  });

  els.prevPage.addEventListener("click", () => {
    if (state.currentPage > 1) {
      state.currentPage -= 1;
      renderFindings();
    }
  });

  els.nextPage.addEventListener("click", () => {
    if (state.currentPage < state.totalPages) {
      state.currentPage += 1;
      renderFindings();
    }
  });

  window.addEventListener("resize", renderCharts);
  window.addEventListener("beforeunload", closeAssessmentSocket);
}

async function boot() {
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  if (!isLocalHost && els.apiBase.value.trim() === "http://localhost:8000") {
    els.apiBase.value = window.location.origin;
  }

  setupEvents();
  setCreateModeUI();

  try {
    await loadAssessments();
    if (state.selectedAssessmentId) {
      await loadFindings(state.selectedAssessmentId);
    } else {
      renderFindings();
    }
  } catch (error) {
    els.createStatus.textContent = `Initial load failed: ${error.message}`;
    renderAssessments();
    renderFindings();
  }
}

boot();
