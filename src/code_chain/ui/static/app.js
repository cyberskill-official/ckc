/**
 * Code Knowledge Chain Interactive Dashboard Controller
 */

// Initialize Mermaid.js for client-side rendering
if (window.mermaid) {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'default',
    securityLevel: 'loose',
    flowchart: { curve: 'basis' },
  });
}

// Global App State
const state = {
  currentProject: "",
  indexingSource: null,
  indexingTimerInterval: null,
  indexingSeconds: 0,
  lastQueryResult: "",
  lastImpactResult: "",
  lastTraceResult: "",
  samples: {},
};

document.addEventListener("DOMContentLoaded", async () => {
  setupNavigation();
  setupRepoBar();
  setupIndexing();
  setupQueryTab();
  setupImpactTab();
  setupTraceTab();
  setupArtifactsTab();

  // Dynamically load bundled samples
  await loadBundledSamples();

  // Load saved or default repo
  const input = document.getElementById("repoPathInput");
  const savedRepo = localStorage.getItem("ckc_current_repo");
  const initialRepo = savedRepo || Object.values(state.samples)[0] || "";
  if (initialRepo) {
    input.value = initialRepo;
    loadProjectStatus(initialRepo);
  }
});

/* Navigation & Tabs */
function setupNavigation() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) targetContent.classList.add("active");

      if (targetId === "tab-artifacts") {
        loadArtifacts();
      }
    });
  });
}

/* Error Banner */
function showError(message) {
  const banner = document.getElementById("globalErrorBanner");
  const msg = document.getElementById("globalErrorMessage");
  msg.textContent = message;
  banner.style.display = "flex";
}

function dismissError() {
  const banner = document.getElementById("globalErrorBanner");
  banner.style.display = "none";
}

/* Repository Bar */
async function loadBundledSamples() {
  try {
    const res = await fetch("/api/samples");
    if (!res.ok) return;
    const data = await res.json();
    const container = document.querySelector(".quick-links");
    if (!container) return;

    // Clear static presets and render dynamic ones
    container.innerHTML = "<span>Quick Load:</span>";
    (data.samples || []).forEach(sample => {
      state.samples[sample.id] = sample.path;
      const chip = document.createElement("span");
      chip.className = "link-chip";
      chip.textContent = `${sample.name}`;
      chip.title = sample.path;
      chip.addEventListener("click", () => {
        document.getElementById("repoPathInput").value = sample.path;
        loadProjectStatus(sample.path);
      });
      container.appendChild(chip);
    });
  } catch (e) {
    console.warn("Could not load bundled samples:", e);
  }
}

function setupRepoBar() {
  const input = document.getElementById("repoPathInput");
  const btnLoad = document.getElementById("btnLoadRepo");

  btnLoad.addEventListener("click", () => {
    const val = input.value.trim();
    if (val) {
      loadProjectStatus(val);
    } else {
      showError("Please enter a valid directory path.");
    }
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      btnLoad.click();
    }
  });
}

async function loadProjectStatus(path) {
  dismissError();
  state.currentProject = path;
  localStorage.setItem("ckc_current_repo", path);

  const badge = document.getElementById("readinessBadge");
  badge.className = "badge";
  badge.innerHTML = '<span class="spinner"></span> Checking...';

  try {
    const res = await fetch(`/api/status?project=${encodeURIComponent(path)}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to load project status");
    }
    const data = await res.json();
    window.__ckcLastStatusMeta = {
      llm: data.llm,
      local_docs_count: data.local_docs_count,
    };
    renderStatus(data.status);
  } catch (err) {
    badge.className = "badge badge-missing";
    badge.innerHTML = '<span>●</span> Offline / Invalid';
    showError(err.message);
  }
}

function renderStatus(status) {
  const badge = document.getElementById("readinessBadge");
  const readyCount = status.ready_count || 0;

  if (readyCount === 3) {
    badge.className = "badge badge-ready";
    badge.innerHTML = "<span>●</span> 3/3 Engines Ready";
  } else if (readyCount > 0) {
    badge.className = "badge badge-partial";
    badge.innerHTML = `<span>●</span> ${readyCount}/3 Engines Ready`;
  } else {
    badge.className = "badge badge-missing";
    badge.innerHTML = "<span>●</span> Not Indexed";
  }

  // Graphify
  const g = status.graphify || {};
  const gBadge = document.getElementById("statusGraphifyBadge");
  gBadge.className = `badge ${g.indexed ? 'badge-ready' : 'badge-missing'}`;
  gBadge.textContent = g.indexed ? "Indexed" : "Missing";
  document.getElementById("statGraphifyNodes").textContent = g.node_count || 0;
  document.getElementById("statGraphifyDetails").textContent =
    `Communities: ${g.details?.communities_count || 0} | Edges: ${g.edge_count || 0} | Local docs: ${g.details?.local_docs_count || 0}`;

  const llmChip = document.getElementById("llmStatusChip");
  if (llmChip && window.__ckcLastStatusMeta) {
    const llm = window.__ckcLastStatusMeta.llm;
    if (llm?.configured) {
      llmChip.textContent = `LLM: ${llm.model || "configured"} @ ${llm.base_url || "?"}`;
    } else {
      llmChip.textContent = "LLM: not configured";
    }
  }

  // GitNexus
  const gn = status.gitnexus || {};
  const gnBadge = document.getElementById("statusGitNexusBadge");
  gnBadge.className = `badge ${gn.indexed ? 'badge-ready' : 'badge-missing'}`;
  gnBadge.textContent = gn.indexed ? "Indexed" : "Missing";
  document.getElementById("statGitNexusNodes").textContent = gn.node_count || (gn.indexed ? "Ready" : 0);
  document.getElementById("statGitNexusDetails").textContent =
    gn.indexed ? "AST Call Graph & Blast Radius Ready" : "KùzuDB: Run indexing to build";

  // CodeGraph
  const cg = status.codegraph || {};
  const cgBadge = document.getElementById("statusCodeGraphBadge");
  cgBadge.className = `badge ${cg.indexed ? 'badge-ready' : 'badge-missing'}`;
  cgBadge.textContent = cg.indexed ? "Indexed" : "Missing";
  document.getElementById("statCodeGraphNodes").textContent = cg.node_count || (cg.indexed ? "Ready" : 0);
  document.getElementById("statCodeGraphDetails").textContent =
    cg.indexed ? "Symbol Table & Source Cache Active" : "Symbol Cache: Run indexing to build";
}

/* Indexing & Live Streaming */
function setupIndexing() {
  const btnStart = document.getElementById("btnStartIndex");
  const btnCancel = document.getElementById("btnCancelIndex");
  const btnClear = document.getElementById("btnClearTerminal");
  const terminal = document.getElementById("terminalBody");
  const timer = document.getElementById("indexingTimer");

  btnClear.addEventListener("click", () => {
    terminal.innerHTML = '<div class="terminal-line" style="color: var(--text-muted);">Terminal cleared.</div>';
  });

  btnStart.addEventListener("click", () => {
    const path = state.currentProject;
    if (!path) {
      showError("Please enter and verify a repository path first.");
      return;
    }
    const multimodal = document.getElementById("checkMultimodal").checked;
    const force = document.getElementById("checkForceIndex")?.checked || false;
    startIndexingStream(path, multimodal, force);
  });

  btnCancel.addEventListener("click", async () => {
    if (!state.currentProject) return;
    try {
      await fetch("/api/index/cancel", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_path: state.currentProject }),
      });
      appendTerminalLine("Cancellation request sent...", "log-error");
    } catch (err) {
      appendTerminalLine(`Error cancelling: ${err}`, "log-error");
    }
  });
}

function startIndexingStream(projectPath, multimodal, force = false) {
  const btnStart = document.getElementById("btnStartIndex");
  const btnCancel = document.getElementById("btnCancelIndex");
  const terminal = document.getElementById("terminalBody");
  const timer = document.getElementById("indexingTimer");

  btnStart.style.display = "none";
  btnCancel.style.display = "inline-flex";
  terminal.innerHTML = "";

  state.indexingSeconds = 0;
  clearInterval(state.indexingTimerInterval);
  state.indexingTimerInterval = setInterval(() => {
    state.indexingSeconds++;
    const m = String(Math.floor(state.indexingSeconds / 60)).padStart(2, '0');
    const s = String(state.indexingSeconds % 60).padStart(2, '0');
    timer.textContent = `${m}:${s}`;
  }, 1000);

  const url = `/api/index/stream?project=${encodeURIComponent(projectPath)}&multimodal=${multimodal}&force=${force}`;
  const es = new EventSource(url);
  state.indexingSource = es;

  es.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      handleStreamEvent(data);
    } catch (e) {
      appendTerminalLine(event.data);
    }
  };

  es.onerror = () => {
    appendTerminalLine("Stream closed or encountered an error.", "log-error");
    stopIndexingUI();
    loadProjectStatus(projectPath);
  };
}

function handleStreamEvent(data) {
  if (data.event === "start") {
    appendTerminalLine(`[CKC] ${data.message}`, "log-success");
  } else if (data.event === "step_start") {
    appendTerminalLine(`\n-----------------------------------------------------------`, "text-secondary");
    appendTerminalLine(`[Step ${data.step}/${data.total_steps}] ${data.label}...`, `log-${data.engine}`);
  } else if (data.event === "log") {
    appendTerminalLine(data.line, `log-${data.engine}`);
  } else if (data.event === "step_finish") {
    const statusText = data.success ? "✓ Succeeded" : `✗ Exited with code ${data.returncode}`;
    appendTerminalLine(`[${data.engine}] ${statusText}`, data.success ? "log-success" : "log-error");
  } else if (data.event === "step_error") {
    appendTerminalLine(`[${data.engine}] Error: ${data.error}`, "log-error");
  } else if (data.event === "cancelled") {
    appendTerminalLine(`[CKC] ${data.message}`, "log-error");
    stopIndexingUI();
    loadProjectStatus(state.currentProject);
  } else if (data.event === "complete") {
    appendTerminalLine(`\n===========================================================`, "log-success");
    appendTerminalLine(`[CKC] 3-Tier Indexing Completed! Readiness: ${data.status?.ready_count}/3 engines.`, "log-success");
    stopIndexingUI();
    loadProjectStatus(state.currentProject);
  }
}

function appendTerminalLine(text, className = "") {
  const terminal = document.getElementById("terminalBody");
  const div = document.createElement("div");
  div.className = `terminal-line ${className}`;
  div.textContent = text;
  terminal.appendChild(div);
  terminal.scrollTop = terminal.scrollHeight;
}

function stopIndexingUI() {
  if (state.indexingSource) {
    state.indexingSource.close();
    state.indexingSource = null;
  }
  clearInterval(state.indexingTimerInterval);
  document.getElementById("btnStartIndex").style.display = "inline-flex";
  document.getElementById("btnCancelIndex").style.display = "none";
}

/* Query Tab */
function setupQueryTab() {
  const input = document.getElementById("queryInput");
  const btnRun = document.getElementById("btnRunQuery");
  const btnCopy = document.getElementById("btnCopyQuery");

  btnRun.addEventListener("click", () => runQuery(input.value.trim()));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnRun.click();
  });

  document.querySelectorAll(".link-chip[data-query]").forEach(chip => {
    chip.addEventListener("click", () => {
      input.value = chip.getAttribute("data-query");
      btnRun.click();
    });
  });

  btnCopy.addEventListener("click", () => {
    if (state.lastQueryResult) {
      navigator.clipboard.writeText(state.lastQueryResult);
      btnCopy.textContent = "✓ Copied!";
      setTimeout(() => { btnCopy.textContent = "📋 Copy LLM Prompt Context"; }, 2000);
    }
  });
}

async function runQuery(queryText) {
  if (!queryText) {
    showError("Please enter a query or concept.");
    return;
  }
  if (!state.currentProject) {
    showError("Please load a repository first.");
    return;
  }

  const loading = document.getElementById("queryLoading");
  const empty = document.getElementById("queryEmpty");
  const container = document.getElementById("queryResultContainer");
  const resultPane = document.getElementById("queryMarkdownResult");

  loading.style.display = "block";
  empty.style.display = "none";
  container.style.display = "none";
  dismissError();

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_path: state.currentProject,
        query: queryText,
        use_llm: document.getElementById("checkQueryLlm")?.checked !== false,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Query failed");
    }
    const data = await res.json();
    state.lastQueryResult = data.synthesized_context;

    resultPane.innerHTML = window.marked ? marked.parse(data.synthesized_context) : `<pre>${data.synthesized_context}</pre>`;
    loading.style.display = "none";
    container.style.display = "block";
  } catch (err) {
    loading.style.display = "none";
    empty.style.display = "block";
    showError(err.message);
  }
}

/* Impact Tab */
function setupImpactTab() {
  const input = document.getElementById("impactSymbolInput");
  const btnRun = document.getElementById("btnRunImpact");
  const btnCopy = document.getElementById("btnCopyImpact");

  btnRun.addEventListener("click", () => runImpact(input.value.trim()));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") btnRun.click();
  });

  document.querySelectorAll(".link-chip[data-impact]").forEach(chip => {
    chip.addEventListener("click", () => {
      input.value = chip.getAttribute("data-impact");
      btnRun.click();
    });
  });

  btnCopy.addEventListener("click", () => {
    if (state.lastImpactResult) {
      navigator.clipboard.writeText(state.lastImpactResult);
      btnCopy.textContent = "✓ Copied!";
      setTimeout(() => { btnCopy.textContent = "📋 Copy Impact Report"; }, 2000);
    }
  });
}

async function runImpact(symbol) {
  if (!symbol) {
    showError("Please specify a symbol name to analyze.");
    return;
  }
  if (!state.currentProject) {
    showError("Please load a repository first.");
    return;
  }

  const loading = document.getElementById("impactLoading");
  const empty = document.getElementById("impactEmpty");
  const container = document.getElementById("impactResultContainer");
  const resultPane = document.getElementById("impactMarkdownResult");

  loading.style.display = "block";
  empty.style.display = "none";
  container.style.display = "none";
  dismissError();

  try {
    const res = await fetch("/api/impact", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_path: state.currentProject,
        symbol,
        use_llm: document.getElementById("checkImpactLlm")?.checked !== false,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Impact analysis failed");
    }
    const data = await res.json();
    state.lastImpactResult = data.synthesized_report;

    resultPane.innerHTML = window.marked ? marked.parse(data.synthesized_report) : `<pre>${data.synthesized_report}</pre>`;
    loading.style.display = "none";
    container.style.display = "block";
  } catch (err) {
    loading.style.display = "none";
    empty.style.display = "block";
    showError(err.message);
  }
}

/* Trace Tab */
function setupTraceTab() {
  const fromInput = document.getElementById("traceFromInput");
  const toInput = document.getElementById("traceToInput");
  const btnRun = document.getElementById("btnRunTrace");
  const btnCopy = document.getElementById("btnCopyTrace");

  btnRun.addEventListener("click", () => runTrace(fromInput.value.trim(), toInput.value.trim()));

  document.querySelectorAll(".link-chip[data-trace-from]").forEach(chip => {
    chip.addEventListener("click", () => {
      fromInput.value = chip.getAttribute("data-trace-from");
      toInput.value = chip.getAttribute("data-trace-to");
      btnRun.click();
    });
  });

  btnCopy.addEventListener("click", () => {
    if (state.lastTraceResult) {
      navigator.clipboard.writeText(state.lastTraceResult);
      btnCopy.textContent = "✓ Copied!";
      setTimeout(() => { btnCopy.textContent = "📋 Copy Trace Dossier"; }, 2000);
    }
  });
}

async function runTrace(fromSymbol, toSymbol) {
  if (!fromSymbol || !toSymbol) {
    showError("Both source and destination symbols are required for tracing.");
    return;
  }
  if (!state.currentProject) {
    showError("Please load a repository first.");
    return;
  }

  const loading = document.getElementById("traceLoading");
  const empty = document.getElementById("traceEmpty");
  const container = document.getElementById("traceResultContainer");
  const resultPane = document.getElementById("traceMarkdownResult");
  const mermaidBox = document.getElementById("mermaidRenderBox");

  loading.style.display = "block";
  empty.style.display = "none";
  container.style.display = "none";
  mermaidBox.innerHTML = "";
  dismissError();

  try {
    const res = await fetch("/api/trace", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        project_path: state.currentProject,
        from_symbol: fromSymbol,
        to_symbol: toSymbol,
        use_llm: document.getElementById("checkTraceLlm")?.checked !== false,
      }),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Trace execution failed");
    }
    const data = await res.json();
    state.lastTraceResult = data.synthesized_flow;

    // Render Mermaid diagram if available
    const mermaidMatch = data.synthesized_flow.match(/```mermaid\n([\s\S]*?)```/);
    if (mermaidMatch && window.mermaid) {
      try {
        const graphDefinition = mermaidMatch[1];
        const { svg } = await mermaid.render('mermaidGraphSvg', graphDefinition);
        mermaidBox.innerHTML = svg;
      } catch (me) {
        mermaidBox.innerHTML = `<pre style="color: red;">Mermaid render notice: ${me.message}</pre>`;
      }
    }

    resultPane.innerHTML = window.marked ? marked.parse(data.synthesized_flow) : `<pre>${data.synthesized_flow}</pre>`;
    loading.style.display = "none";
    container.style.display = "block";
  } catch (err) {
    loading.style.display = "none";
    empty.style.display = "block";
    showError(err.message);
  }
}

/* Artifacts Tab */
async function loadArtifacts() {
  const grid = document.getElementById("artifactsGrid");
  const viewer = document.getElementById("artifactViewerContainer");
  grid.innerHTML = '<div style="color: var(--text-secondary); padding: 16px;">Scanning project artifacts...</div>';
  viewer.style.display = "none";

  if (!state.currentProject) {
    grid.innerHTML = '<div style="color: var(--text-secondary); padding: 16px;">Please load a repository first.</div>';
    return;
  }

  try {
    const res = await fetch(`/api/artifacts?project=${encodeURIComponent(state.currentProject)}`);
    if (!res.ok) throw new Error("Failed to load artifacts");
    const data = await res.json();
    renderArtifacts(data.artifacts);
  } catch (err) {
    grid.innerHTML = `<div style="color: var(--accent-red); padding: 16px;">Error: ${err.message}</div>`;
  }
}

function renderArtifacts(artifacts) {
  const grid = document.getElementById("artifactsGrid");
  grid.innerHTML = "";

  if (!artifacts || artifacts.length === 0) {
    grid.innerHTML = '<div class="empty-state" style="grid-column: 1 / -1;"><p>No generated artifacts found. Run indexing to generate knowledge graph files.</p></div>';
    return;
  }

  artifacts.forEach(art => {
    const card = document.createElement("div");
    card.className = "card";
    card.style.cursor = "pointer";
    card.innerHTML = `
      <div class="card-header">
        <span class="card-title" style="font-size: 14px;">📄 ${art.label}</span>
        <span class="badge badge-ready">Ready</span>
      </div>
      <div style="font-family: var(--font-mono); font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
        ${art.relative_path}
      </div>
      <div style="font-size: 11px; color: var(--text-muted);">
        Size: ${(art.size_bytes / 1024).toFixed(1)} KB
      </div>
    `;
    card.addEventListener("click", () => viewArtifact(art.relative_path, art.label));
    grid.appendChild(card);
  });
}

async function viewArtifact(relativePath, label) {
  const viewer = document.getElementById("artifactViewerContainer");
  const title = document.getElementById("artifactViewerTitle");
  const content = document.getElementById("artifactViewerContent");

  title.textContent = `Viewing: ${label} (${relativePath})`;
  content.textContent = "Loading file content...";
  viewer.style.display = "block";
  viewer.scrollIntoView({ behavior: "smooth" });

  try {
    const res = await fetch(`/api/artifacts/content?project=${encodeURIComponent(state.currentProject)}&file=${encodeURIComponent(relativePath)}`);
    if (!res.ok) throw new Error("Failed to read artifact");
    const data = await res.json();
    if (data.is_binary) {
      content.textContent = data.message || "Binary artifact listed only; contents are not displayed.";
    } else {
      content.textContent = data.content;
    }
  } catch (err) {
    content.textContent = `Error reading file: ${err.message}`;
  }
}

function closeArtifactViewer() {
  document.getElementById("artifactViewerContainer").style.display = "none";
}

function setupArtifactsTab() {
  document.getElementById("btnRefreshArtifacts").addEventListener("click", loadArtifacts);
}
