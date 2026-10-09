// Olive Harvester dashboard frontend.
// Polls GET /api/status every second and re-renders the whole UI from the
// snapshot it gets back; user actions POST to the relevant endpoint and
// then render whatever snapshot that endpoint returns immediately (no
// need to wait for the next poll tick).

const state = {
  selectedBranch: null,
  branches: [],
  resolvedAlertIds: new Set(),
};

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Request failed (${res.status})`);
  }
  return data;
}

function showToast(message) {
  const toast = el("toast");
  toast.textContent = message;
  toast.style.display = "block";
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => (toast.style.display = "none"), 3500);
}

// ---------------------------------------------------------------------
// Branches
// ---------------------------------------------------------------------

async function loadBranches() {
  state.branches = await api("/branches");
  renderBranches(null);
}

function renderBranches(selected) {
  const grid = el("branch-grid");
  grid.innerHTML = "";
  state.branches.forEach((b) => {
    const btn = document.createElement("button");
    btn.className = "branch-btn" + (b.id === selected ? " selected" : "");
    btn.textContent = b.id;
    btn.title = b.label;
    btn.disabled = state.harvesting === true;
    btn.addEventListener("click", () => selectBranch(b.id));
    grid.appendChild(btn);
  });
}

async function selectBranch(branchId) {
  try {
    const snapshot = await api("/select-branch", {
      method: "POST",
      body: JSON.stringify({ branch_id: branchId }),
    });
    render(snapshot);
  } catch (err) {
    showToast(err.message);
  }
}

// ---------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------

async function doCapture() {
  try {
    const snapshot = await api("/capture", { method: "POST" });
    render(snapshot);
  } catch (err) {
    showToast(err.message);
  }
}

async function doStart() {
  const overrides = {
    frequency_hz: parseFloat(el("param-frequency").value),
    amplitude_mm: parseFloat(el("param-amplitude").value),
    duration_s: parseFloat(el("param-duration").value),
  };
  try {
    const snapshot = await api("/harvest/start", {
      method: "POST",
      body: JSON.stringify(overrides),
    });
    render(snapshot);
  } catch (err) {
    showToast(err.message);
  }
}

async function doStop() {
  try {
    const snapshot = await api("/harvest/stop", { method: "POST" });
    render(snapshot);
    loadHistory();
  } catch (err) {
    showToast(err.message);
  }
}

async function resolveAlert(id) {
  try {
    const snapshot = await api(`/alerts/${id}/resolve`, { method: "POST" });
    render(snapshot);
  } catch (err) {
    showToast(err.message);
  }
}

// ---------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------

function render(snapshot) {
  const status = snapshot.status;
  state.harvesting = status === "harvesting";

  // Status badge + system status card
  const badge = el("status-badge");
  badge.textContent = status.toUpperCase();
  badge.className = `status-badge status-${status}`;
  el("sys-status").textContent = status.charAt(0).toUpperCase() + status.slice(1);
  el("sys-branch").textContent = snapshot.current_branch || "None";
  el("sys-updated").textContent = new Date(snapshot.timestamp).toLocaleTimeString();

  // Branch grid selection + disabled state
  renderBranches(snapshot.current_branch);

  // Camera / capture
  el("btn-capture").disabled = !snapshot.current_branch || status === "harvesting";
  if (snapshot.capture) {
    const img = el("capture-image");
    img.src = snapshot.capture.image_url + `?t=${Date.now()}`;
    img.style.display = "block";
    el("capture-placeholder").style.display = "none";
  }

  // Maturity + recommended/active parameters
  const params = snapshot.parameters;
  const badgeEl = el("maturity-badge");
  const advisoryEl = el("param-advisory");
  if (params) {
    badgeEl.textContent = params.maturity_class.replace("_", " ");
    badgeEl.className = `maturity-badge maturity-${params.maturity_class}`;
    el("maturity-confidence").textContent = `${Math.round(params.confidence * 100)}% colour-match score`;

    if (!state.harvesting) {
      el("param-frequency").value = params.frequency_hz;
      el("param-amplitude").value = params.amplitude_mm;
      el("param-duration").value = params.duration_s;
    }

    if (params.advisory) {
      advisoryEl.textContent = params.advisory;
      advisoryEl.style.display = "block";
    } else {
      advisoryEl.style.display = "none";
    }
  } else {
    badgeEl.textContent = "—";
    badgeEl.className = "maturity-badge maturity-none";
    el("maturity-confidence").textContent = "";
    advisoryEl.style.display = "none";
  }

  el("btn-start").disabled = status !== "assessed";
  el("btn-stop").disabled = status !== "harvesting";
  ["param-frequency", "param-amplitude", "param-duration"].forEach((id) => {
    el(id).disabled = state.harvesting;
  });

  // Progress bar
  const target = snapshot.target_duration_s || 0;
  const elapsed = snapshot.elapsed_s || 0;
  const pct = target > 0 ? Math.min(100, (elapsed / target) * 100) : 0;
  el("harvest-progress").style.width = `${pct}%`;
  el("progress-label").textContent = `${elapsed.toFixed(1)}s / ${target.toFixed(1)}s`;

  // Sensors + mass
  el("sensor-vibration").textContent = snapshot.sensors.vibration_hz.toFixed(1);
  el("sensor-current").textContent = snapshot.sensors.motor_current_a.toFixed(2);
  el("mass-value").textContent = snapshot.harvested_mass_g.toFixed(1);

  // Alerts
  renderAlerts(snapshot.alerts);
}

function renderAlerts(alerts) {
  const list = el("alerts-list");
  if (!alerts || alerts.length === 0) {
    list.innerHTML = '<li class="alert-empty">No alerts yet.</li>';
    return;
  }
  list.innerHTML = "";
  alerts.forEach((a) => {
    const li = document.createElement("li");
    li.className = `sev-${a.severity}` + (a.resolved ? " resolved" : "");
    const time = new Date(a.raised_at).toLocaleTimeString();
    li.innerHTML = `
      <span class="alert-text">${a.message}<span class="alert-time">${a.severity.toUpperCase()} · ${time}</span></span>
    `;
    if (!a.resolved) {
      const btn = document.createElement("button");
      btn.className = "alert-resolve-btn";
      btn.textContent = "Resolve";
      btn.addEventListener("click", () => resolveAlert(a.id));
      li.appendChild(btn);
    }
    list.appendChild(li);
  });
}

async function loadHistory() {
  try {
    const rows = await api("/history?limit=20");
    renderHistory(rows);
  } catch (err) {
    // non-fatal
  }
}

function renderHistory(rows) {
  const body = el("history-body");
  if (!rows || rows.length === 0) {
    body.innerHTML = '<tr><td colspan="9" class="empty-row">No sessions recorded yet.</td></tr>';
    return;
  }
  body.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    const ended = new Date(r.ended_at).toLocaleString();
    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.branch_id}</td>
      <td>${(r.maturity_class || "").replace("_", " ")}</td>
      <td>${r.frequency_hz ?? "—"}</td>
      <td>${r.amplitude_mm ?? "—"}</td>
      <td>${r.duration_actual_s ?? "—"}</td>
      <td>${r.harvested_mass_g ?? "—"}</td>
      <td><span class="status-pill-cell status-pill-${r.status}">${r.status}</span></td>
      <td>${ended}</td>
    `;
    body.appendChild(tr);
  });
}

// ---------------------------------------------------------------------
// Polling loop
// ---------------------------------------------------------------------

let lastStatus = null;

async function pollStatus() {
  try {
    const snapshot = await api("/status");
    render(snapshot);
    if (lastStatus === "harvesting" && snapshot.status !== "harvesting") {
      loadHistory(); // a harvest just auto-completed
    }
    lastStatus = snapshot.status;
  } catch (err) {
    // transient network error while polling — ignore, try again next tick
  }
}

function init() {
  el("btn-capture").addEventListener("click", doCapture);
  el("btn-start").addEventListener("click", doStart);
  el("btn-stop").addEventListener("click", doStop);

  loadBranches();
  loadHistory();
  pollStatus();
  setInterval(pollStatus, 1000);
}

document.addEventListener("DOMContentLoaded", init);
