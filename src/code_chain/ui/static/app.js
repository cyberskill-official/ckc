// ==========================================================================
// CKC Graph-First Explorer Engine (100% 3D WebGL Spatial Universe)
// Designed with Linear/Raycast/Cursor Professional Developer Ergonomics
// ==========================================================================

const state = {
    currentProject: localStorage.getItem('ckc_project_path') || '',
    uiToken: localStorage.getItem('ckc_ui_token') || '',
    useLlm: localStorage.getItem('ckc_use_llm') !== '0',
    graph3d: null,
    selectedNode: null,
    traceSource: null,
    graphData: null,
    communities: [],
    filters: { code: true, doc: true, schema: true, test: true },
    isAutoRotating: false,
    indexingAbort: null,
    indexingCleanClose: false,
    inFlight: false,
    drawerOpen: false,
    drawerTab: 'terminal',
    lastResults: '',
    highlightNodes: new Set(),
    highlightLinks: new Set(),
    hoverNode: null,
    palette: [
        '#38bdf8', '#818cf8', '#c084fc', '#f472b6', '#fb7185',
        '#f59e0b', '#10b981', '#34d399', '#2dd4bf', '#22d3ee',
        '#a78bfa', '#e879f9', '#fb923c', '#4ade80', '#60a5fa', '#94a3b8'
    ]
};

// Expose state globally for DevTools inspection & automated verification
window.state = state;

if (window.mermaid) {
    mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'dark'
    });
}

const els = {
    // Header & Popovers
    projectInput: document.getElementById('project-path'),
    uiTokenInput: document.getElementById('ui-token'),
    samplePicker: document.getElementById('sample-picker'),
    loadBtn: document.getElementById('load-btn'),
    readyBadge: document.getElementById('ready-badge'),
    readyBadgeText: document.querySelector('#ready-badge .badge-text'),
    docsChip: document.getElementById('docs-chip'),
    llmChip: document.getElementById('llm-chip'),
    autoRotateBtn: document.getElementById('auto-rotate-btn'),
    fitBtn: document.getElementById('fit-btn'),
    resetCamBtn: document.getElementById('reset-cam-btn'),

    projectPillBtn: document.getElementById('project-pill-btn'),
    currentProjectLabel: document.getElementById('current-project-label'),
    projectPopover: document.getElementById('project-popover'),
    closeProjectPopoverBtn: document.getElementById('close-project-popover-btn'),
    layersToggleBtn: document.getElementById('layers-toggle-btn'),
    layersPopover: document.getElementById('layers-popover'),
    closeLayersPopoverBtn: document.getElementById('close-layers-popover-btn'),
    headerIndexBtn: document.getElementById('header-index-btn'),
    indexPopover: document.getElementById('index-popover'),
    closeIndexPopoverBtn: document.getElementById('close-index-popover-btn'),

    // Filters & Communities
    filterCode: document.getElementById('filter-code'),
    filterDoc: document.getElementById('filter-doc'),
    filterSchema: document.getElementById('filter-schema'),
    filterTest: document.getElementById('filter-test'),
    countCode: document.getElementById('count-code'),
    countDoc: document.getElementById('count-doc'),
    countSchema: document.getElementById('count-schema'),
    countTest: document.getElementById('count-test'),
    communityList: document.getElementById('community-list'),
    commTotalBadge: document.getElementById('comm-total-badge'),
    runIndexBtn: document.getElementById('run-index-btn'),
    cancelIndexBtn: document.getElementById('cancel-index-btn'),
    forceIndex: document.getElementById('force-index'),
    multimodalIndex: document.getElementById('multimodal-index'),
    useLlm: document.getElementById('use-llm'),
    opsHistory: document.getElementById('ops-history'),

    // Viewport & HUD
    graphViewport: document.getElementById('graph-viewport'),
    container3d: document.getElementById('graph-3d'),
    commandBar: document.getElementById('command-bar'),
    clearOverlaysBtn: document.getElementById('clear-overlays-btn'),
    modeBadges: document.querySelectorAll('.mode-badge'),

    // Right Panel Context Inspector
    contextPanel: document.getElementById('context-panel'),
    closePanelBtn: document.getElementById('close-panel-btn'),
    nodeDetails: document.getElementById('node-details'),
    nodeLabel: document.getElementById('node-label'),
    nodeCategory: document.getElementById('node-category'),
    nodeTypeBadge: document.getElementById('node-type-badge'),
    nodeSource: document.getElementById('node-source'),
    nodeCommunity: document.getElementById('node-community'),
    nodeDegree: document.getElementById('node-degree'),
    nodeConnections: document.getElementById('node-connections'),
    copySymbolNameBtn: document.getElementById('copy-symbol-name-btn'),
    actionImpact: document.getElementById('action-impact'),
    actionTrace: document.getElementById('action-trace'),
    actionQuery: document.getElementById('action-query'),

    // Bottom Drawer
    drawer: document.getElementById('drawer'),
    drawerToggle: document.getElementById('drawer-toggle'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    terminalOutput: document.getElementById('terminal-output'),
    resultsOutput: document.getElementById('results-output'),
    copyResultsBtn: document.getElementById('copy-results-btn')
};

// ==========================================================================
// App Initialization
// ==========================================================================

function init() {
    if (els.projectInput) els.projectInput.value = state.currentProject;
    if (els.uiTokenInput) els.uiTokenInput.value = state.uiToken;
    if (els.useLlm) els.useLlm.checked = state.useLlm;

    updateProjectLabel();
    init3DGraph();
    setupEventListeners();
    loadSamples();

    if (state.currentProject) {
        loadProject();
    }
}

function updateProjectLabel() {
    if (!els.currentProjectLabel) return;
    if (state.currentProject) {
        const clean = state.currentProject.replace(/[/\\]+$/, '');
        const parts = clean.split(/[/\\]/);
        const name = parts[parts.length - 1] || clean;
        els.currentProjectLabel.textContent = name;
        els.currentProjectLabel.title = state.currentProject;
    } else {
        els.currentProjectLabel.textContent = 'Select Project…';
        els.currentProjectLabel.title = 'Click to choose repository';
    }
}

function closeAllPopovers() {
    if (els.projectPopover) els.projectPopover.classList.add('closed');
    if (els.layersPopover) els.layersPopover.classList.add('closed');
    if (els.indexPopover) els.indexPopover.classList.add('closed');
}

function persistUseLlmFromInput() {
    if (!els.useLlm) return;
    state.useLlm = !!els.useLlm.checked;
    localStorage.setItem('ckc_use_llm', state.useLlm ? '1' : '0');
}

function persistUiTokenFromInput() {
    if (!els.uiTokenInput) return;
    state.uiToken = (els.uiTokenInput.value || '').trim();
    if (state.uiToken) {
        localStorage.setItem('ckc_ui_token', state.uiToken);
    } else {
        localStorage.removeItem('ckc_ui_token');
    }
}

function authHeaders(extra) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, extra || {});
    if (state.uiToken) {
        headers['Authorization'] = `Bearer ${state.uiToken}`;
        headers['X-CKC-Token'] = state.uiToken;
    }
    return headers;
}

function formatApiDetail(detail) {
    if (detail == null) return 'Unknown error';
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail)) {
        return detail.map((item) => {
            if (typeof item === 'string') return item;
            if (item && typeof item === 'object') {
                const loc = Array.isArray(item.loc) ? item.loc.join('.') : '';
                const msg = item.msg || JSON.stringify(item);
                return loc ? `${loc}: ${msg}` : msg;
            }
            return String(item);
        }).join('; ');
    }
    if (typeof detail === 'object') return JSON.stringify(detail);
    return String(detail);
}

async function apiFetch(url, options = {}) {
    const defaultHeaders = authHeaders(options.headers);
    const res = await fetch(url, { ...options, credentials: 'omit', headers: defaultHeaders });
    if (!res.ok) {
        let errMessage = `HTTP ${res.status} ${res.statusText}`;
        try {
            const errData = await res.json();
            if (errData && errData.detail) {
                errMessage = formatApiDetail(errData.detail);
            }
        } catch (_) {}
        throw new Error(errMessage);
    }
    return res.json();
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function setSafeHtml(el, dirty) {
    if (!el) return;
    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
        el.innerHTML = DOMPurify.sanitize(dirty);
    } else {
        el.textContent = dirty;
    }
}

function setBusy(busy) {
    state.inFlight = busy;
    if (els.loadBtn) els.loadBtn.disabled = busy;
    if (els.runIndexBtn) els.runIndexBtn.disabled = busy;
    if (els.commandBar) els.commandBar.disabled = busy;
}

// ==========================================================================
// 3D Force-Directed Graph Engine
// ==========================================================================

function init3DGraph() {
    if (!els.container3d || !window.ForceGraph3D) return;

    state.graph3d = ForceGraph3D()(els.container3d)
        .backgroundColor('#0c0e14')
        .showNavInfo(false)
        .nodeRelSize(4)
        .nodeResolution(16)
        .nodeVal(node => Math.max(3, Math.sqrt(node.degree || 1) * 2.2 + 2.5))
        .nodeColor(node => {
            if (node.__impactTarget) return '#ef4444';
            if (node.__impacted) return '#f59e0b';
            if (node.__tracePath) return '#38bdf8';
            if (state.highlightNodes.size > 0 && !state.highlightNodes.has(node.id)) {
                return 'rgba(255, 255, 255, 0.08)';
            }
            if (node.category === 'doc') return '#a855f7';
            if (node.category === 'schema') return '#f59e0b';
            if (node.category === 'test') return '#10b981';
            return getNodeCommunityColor(node.community);
        })
        .nodeLabel(node => {
            const cat = (node.category || 'code').toUpperCase();
            return `<div style="background:#131620;border:1px solid rgba(255,255,255,0.14);border-radius:6px;padding:6px 10px;font-family:'IBM Plex Sans',sans-serif;box-shadow:0 4px 16px rgba(0,0,0,0.5);">
                <div style="font-weight:700;font-size:13px;color:#f3f4f6;font-family:'JetBrains Mono',monospace;">${escapeHtml(node.label || node.id)}</div>
                <div style="font-size:11px;color:#9ca3af;margin-top:2px;">${cat} &bull; ${node.degree || 0} connections</div>
            </div>`;
        })
        .nodeOpacity(0.95)
        .linkColor(link => {
            if (link.__highlight) return '#38bdf8';
            if (link.__trace) return '#38bdf8';
            if (link.__impact) return '#ef4444';
            if (state.highlightNodes.size > 0) return 'rgba(255, 255, 255, 0.03)';
            return 'rgba(255, 255, 255, 0.12)';
        })
        .linkWidth(link => {
            if (link.__highlight || link.__trace || link.__impact) return 2.5;
            return 0.8;
        })
        .linkDirectionalParticles(link => {
            if (link.__trace || link.__impact) return 4;
            if (link.__highlight) return 2;
            return 0;
        })
        .linkDirectionalParticleWidth(link => (link.__trace || link.__impact ? 3.5 : 2))
        .linkDirectionalParticleSpeed(link => (link.__trace ? 0.012 : 0.007))
        .onNodeClick((node, evt) => {
            if (evt && evt.shiftKey) {
                handleShiftClick(node);
            } else {
                selectNode(node);
            }
        })
        .onNodeHover(node => {
            state.hoverNode = node || null;
            if (state.selectedNode) return;

            const links = state.graph3d ? state.graph3d.graphData().links : [];
            const highlightNodes = new Set();
            const highlightLinks = new Set();

            if (node) {
                highlightNodes.add(node.id);
                links.forEach(l => {
                    const s = typeof l.source === 'object' ? l.source.id : l.source;
                    const t = typeof l.target === 'object' ? l.target.id : l.target;
                    if (s === node.id || t === node.id) {
                        highlightNodes.add(s);
                        highlightNodes.add(t);
                        highlightLinks.add(l);
                    }
                });
            }

            state.highlightNodes = highlightNodes;
            state.highlightLinks = highlightLinks;
            state.graph3d.nodeColor(state.graph3d.nodeColor());
            state.graph3d.linkColor(state.graph3d.linkColor());
        })
        .onBackgroundClick(() => {
            clearSelection();
            clearOverlays();
        });

    // Configure 3D Force Simulation
    state.graph3d.d3Force('charge').strength(-180);
    state.graph3d.d3Force('link').distance(45);
}

function getNodeCommunityColor(commId) {
    if (commId == null) return '#38bdf8';
    const idx = Math.abs(Number(commId)) % state.palette.length;
    return state.palette[idx];
}

function flyToNode(node) {
    if (!state.graph3d || !node) return;
    const distance = 80;
    const distRatio = 1 + distance / Math.hypot(node.x || 1, node.y || 1, node.z || 1);

    const nx = (node.x || 0) * distRatio;
    const ny = (node.y || 0) * distRatio;
    const nz = (node.z || 0) * distRatio;

    state.graph3d.cameraPosition(
        { x: nx, y: ny, z: nz },
        { x: node.x || 0, y: node.y || 0, z: node.z || 0 },
        800
    );
}

// ==========================================================================
// Event Listeners & Interactions
// ==========================================================================

function setupEventListeners() {
    // Popovers
    if (els.projectPillBtn && els.projectPopover) {
        els.projectPillBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.projectPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) els.projectPopover.classList.remove('closed');
        });
    }
    if (els.closeProjectPopoverBtn) {
        els.closeProjectPopoverBtn.addEventListener('click', () => {
            if (els.projectPopover) els.projectPopover.classList.add('closed');
        });
    }

    if (els.layersToggleBtn && els.layersPopover) {
        els.layersToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.layersPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) els.layersPopover.classList.remove('closed');
        });
    }
    if (els.closeLayersPopoverBtn) {
        els.closeLayersPopoverBtn.addEventListener('click', () => {
            if (els.layersPopover) els.layersPopover.classList.add('closed');
        });
    }

    if (els.headerIndexBtn && els.indexPopover) {
        els.headerIndexBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) els.indexPopover.classList.remove('closed');
        });
    }
    if (els.readyBadge && els.indexPopover) {
        els.readyBadge.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) els.indexPopover.classList.remove('closed');
        });
    }
    if (els.closeIndexPopoverBtn) {
        els.closeIndexPopoverBtn.addEventListener('click', () => {
            if (els.indexPopover) els.indexPopover.classList.add('closed');
        });
    }

    // Auto-close popovers on outside click
    document.addEventListener('click', (e) => {
        const inProject = els.projectPopover && els.projectPopover.contains(e.target);
        const inLayers = els.layersPopover && els.layersPopover.contains(e.target);
        const inIndex = els.indexPopover && els.indexPopover.contains(e.target);
        const inPill = els.projectPillBtn && els.projectPillBtn.contains(e.target);
        const inLayersBtn = els.layersToggleBtn && els.layersToggleBtn.contains(e.target);
        const inIndexBtn = els.headerIndexBtn && els.headerIndexBtn.contains(e.target);
        const inReadyBadge = els.readyBadge && els.readyBadge.contains(e.target);

        if (!inProject && !inLayers && !inIndex && !inPill && !inLayersBtn && !inIndexBtn && !inReadyBadge) {
            closeAllPopovers();
        }
    });

    // Project Loading
    els.loadBtn.addEventListener('click', () => {
        const val = els.projectInput.value.trim();
        if (!val) return;
        persistUiTokenFromInput();
        state.currentProject = val;
        localStorage.setItem('ckc_project_path', state.currentProject);
        updateProjectLabel();
        closeAllPopovers();
        loadProject();
    });

    els.samplePicker.addEventListener('change', () => {
        if (!els.samplePicker.value) return;
        persistUiTokenFromInput();
        els.projectInput.value = els.samplePicker.value;
        state.currentProject = els.samplePicker.value;
        localStorage.setItem('ckc_project_path', state.currentProject);
        updateProjectLabel();
        closeAllPopovers();
        loadProject();
    });

    els.projectInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') els.loadBtn.click();
    });

    if (els.uiTokenInput) {
        els.uiTokenInput.addEventListener('change', persistUiTokenFromInput);
        els.uiTokenInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                persistUiTokenFromInput();
                els.loadBtn.click();
            }
        });
    }

    if (els.useLlm) {
        els.useLlm.addEventListener('change', persistUseLlmFromInput);
    }

    // HUD Dock Buttons
    if (els.autoRotateBtn) {
        els.autoRotateBtn.addEventListener('click', () => {
            state.isAutoRotating = !state.isAutoRotating;
            els.autoRotateBtn.classList.toggle('active', state.isAutoRotating);
            if (state.graph3d && state.graph3d.controls) {
                state.graph3d.controls().autoRotate = state.isAutoRotating;
                state.graph3d.controls().autoRotateSpeed = 0.8;
            }
        });
    }

    if (els.fitBtn) {
        els.fitBtn.addEventListener('click', fitGraphView);
    }

    if (els.resetCamBtn) {
        els.resetCamBtn.addEventListener('click', resetCameraView);
    }

    // Entity Filters
    ['code', 'doc', 'schema', 'test'].forEach(cat => {
        const checkbox = els[`filter${cat.charAt(0).toUpperCase() + cat.slice(1)}`];
        if (checkbox) {
            checkbox.addEventListener('change', (e) => {
                state.filters[cat] = e.target.checked;
                applyFilters();
            });
        }
    });

    // Command Bar
    els.commandBar.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            handleCommandSubmit(els.commandBar.value.trim());
        }
    });

    els.modeBadges.forEach(badge => {
        badge.addEventListener('click', () => {
            els.modeBadges.forEach(b => b.classList.remove('active'));
            badge.classList.add('active');
        });
    });

    // Context Panel Actions
    els.closePanelBtn.addEventListener('click', () => {
        els.contextPanel.classList.add('closed');
        clearSelection();
    });

    els.actionImpact.addEventListener('click', () => {
        if (state.selectedNode) runImpact(state.selectedNode.label || state.selectedNode.id);
    });

    els.actionTrace.addEventListener('click', () => {
        if (state.selectedNode) {
            state.traceSource = state.selectedNode.id;
            els.commandBar.placeholder = `Select target destination node for trace from ${state.selectedNode.label || state.selectedNode.id}...`;
            els.commandBar.focus();
        }
    });

    els.actionQuery.addEventListener('click', () => {
        if (state.selectedNode) runQuery(`Explain the purpose and architecture of ${state.selectedNode.label || state.selectedNode.id}`);
    });

    if (els.copySymbolNameBtn) {
        els.copySymbolNameBtn.addEventListener('click', () => {
            if (state.selectedNode) {
                navigator.clipboard.writeText(state.selectedNode.label || state.selectedNode.id);
                els.copySymbolNameBtn.title = 'Copied!';
                setTimeout(() => { els.copySymbolNameBtn.title = 'Copy Symbol Name'; }, 1500);
            }
        });
    }

    // Bottom Drawer
    els.drawerToggle.addEventListener('click', (e) => {
        if (e.target.closest('.drawer-tabs') || e.target.closest('#copy-results-btn')) return;
        toggleDrawer();
    });

    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            switchDrawerTab(tab);
            if (!state.drawerOpen) openDrawer();
        });
    });

    els.copyResultsBtn.addEventListener('click', () => {
        if (state.lastResults) {
            navigator.clipboard.writeText(state.lastResults);
            els.copyResultsBtn.textContent = 'Copied!';
            setTimeout(() => {
                els.copyResultsBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg> <span>Copy Markdown</span>`;
            }, 2000);
        }
    });

    els.clearOverlaysBtn.addEventListener('click', clearOverlays);

    // Global Hotkeys
    document.addEventListener('keydown', (e) => {
        const isInput = document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'SELECT');

        if (e.key === 'Escape') {
            closeAllPopovers();
            clearSelection();
            clearOverlays();
            els.contextPanel.classList.add('closed');
        } else if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && !isInput) {
            e.preventDefault();
            els.commandBar.focus();
            els.commandBar.select();
        } else if (e.key === 'f' && !isInput) {
            fitGraphView();
        } else if ((e.key === 'l' || e.key === 'L') && !isInput) {
            e.preventDefault();
            if (els.layersToggleBtn) els.layersToggleBtn.click();
        } else if ((e.key === 'p' || e.key === 'P') && !isInput) {
            e.preventDefault();
            if (els.projectPillBtn) els.projectPillBtn.click();
        }
    });

    // Indexing Actions
    els.runIndexBtn.addEventListener('click', () => {
        closeAllPopovers();
        runIndexing();
    });
    els.cancelIndexBtn.addEventListener('click', cancelIndexing);

    // Window Resize Handler
    window.addEventListener('resize', () => {
        if (state.graph3d && els.container3d) {
            state.graph3d.width(els.graphViewport.clientWidth);
            state.graph3d.height(els.graphViewport.clientHeight);
        }
    });
}

// ==========================================================================
// Camera & Viewport Controls
// ==========================================================================

function fitGraphView() {
    if (state.graph3d) {
        state.graph3d.zoomToFit(800, 40);
    }
}

function resetCameraView() {
    if (state.graph3d) {
        state.graph3d.cameraPosition({ x: 0, y: 0, z: 300 }, { x: 0, y: 0, z: 0 }, 800);
    }
}

// ==========================================================================
// Project Loading & Graph Rendering
// ==========================================================================

async function loadProject() {
    if (!state.currentProject || state.inFlight) return;
    persistUiTokenFromInput();
    setBusy(true);
    try {
        const [statusRes, graphRes] = await Promise.all([
            apiFetch(`/api/status?project=${encodeURIComponent(state.currentProject)}`),
            apiFetch(`/api/graph?project=${encodeURIComponent(state.currentProject)}`),
        ]);

        updateStatus(statusRes);
        renderGraph(graphRes);
    } catch (e) {
        console.error('Failed to load project:', e);
        els.readyBadge.className = 'badge-status badge-error';
        if (els.readyBadgeText) els.readyBadgeText.textContent = 'Error';
        setSafeHtml(
            els.resultsOutput,
            `<span style="color:var(--accent-rose)">Error loading project: ${escapeHtml(e.message)}</span>`
        );
    } finally {
        setBusy(false);
    }
}

function updateStatus(res) {
    if (res.status && res.status.all_ready) {
        els.readyBadge.className = 'badge-status badge-ready';
        if (els.readyBadgeText) els.readyBadgeText.textContent = 'Ready (3/3)';
    } else {
        const count = res.status?.ready_count ?? 0;
        els.readyBadge.className = 'badge-status';
        if (els.readyBadgeText) els.readyBadgeText.textContent = `${count}/3 Engines`;
    }

    const docs = res.local_docs_count;
    if (typeof docs === 'number') {
        els.docsChip.textContent = `Docs: ${docs}`;
        els.docsChip.className = 'badge-chip badge-ready';
    } else {
        els.docsChip.textContent = 'Docs: —';
        els.docsChip.className = 'badge-chip';
    }

    if (res.llm && res.llm.configured) {
        els.llmChip.textContent = `LLM: ${res.llm.model || 'Active'}`;
        els.llmChip.className = 'badge-chip badge-ready';
    } else {
        els.llmChip.textContent = 'LLM: Off';
        els.llmChip.className = 'badge-chip';
        state.useLlm = false;
        if (els.useLlm) els.useLlm.checked = false;
    }
}

function renderGraph(res) {
    if (!res.elements) return;

    state.graphData = res;
    state.communities = res.meta?.communities || [];

    const rawNodes = (res.elements.nodes || []).map(n => n.data);
    const rawLinks = (res.elements.edges || []).map(e => e.data);

    // Update entity filter counts
    const counts = { code: 0, doc: 0, schema: 0, test: 0 };
    rawNodes.forEach(n => {
        const cat = n.category || 'code';
        if (counts[cat] !== undefined) counts[cat]++;
    });
    if (els.countCode) els.countCode.textContent = counts.code;
    if (els.countDoc) els.countDoc.textContent = counts.doc;
    if (els.countSchema) els.countSchema.textContent = counts.schema;
    if (els.countTest) els.countTest.textContent = counts.test;

    // Populate Community List in Layers Popover
    renderCommunityList(state.communities);

    // Filter visible elements
    const visibleNodes = rawNodes.filter(n => state.filters[n.category || 'code']);
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    const visibleLinks = rawLinks.filter(l => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));

    if (state.graph3d) {
        state.graph3d.graphData({
            nodes: visibleNodes,
            links: visibleLinks
        });
        setTimeout(() => { fitGraphView(); }, 600);
    }
}

function renderCommunityList(communities) {
    if (!els.communityList) return;
    els.communityList.innerHTML = '';
    if (els.commTotalBadge) els.commTotalBadge.textContent = `${communities.length} clusters`;

    communities.forEach(c => {
        const li = document.createElement('li');
        li.className = 'community-item';
        const color = getNodeCommunityColor(c.id);
        const samples = (c.sample_labels || []).slice(0, 2).join(', ');

        li.innerHTML = `
            <span class="comm-swatch" style="background-color:${color};"></span>
            <span class="comm-title">Cluster ${c.id}${samples ? ` &bull; ${escapeHtml(samples)}` : ''}</span>
            <span class="comm-size">${c.size}</span>
        `;
        li.addEventListener('click', () => {
            zoomToCommunity(c.id);
            closeAllPopovers();
        });
        els.communityList.appendChild(li);
    });
}

function zoomToCommunity(commId) {
    if (!state.graph3d) return;
    const gNodes = state.graph3d.graphData().nodes.filter(n => n.community === commId);
    if (!gNodes.length) return;

    let sx = 0, sy = 0, sz = 0;
    gNodes.forEach(n => { sx += n.x || 0; sy += n.y || 0; sz += n.z || 0; });
    const cx = sx / gNodes.length;
    const cy = sy / gNodes.length;
    const cz = sz / gNodes.length;

    state.graph3d.cameraPosition(
        { x: cx, y: cy, z: cz + 120 },
        { x: cx, y: cy, z: cz },
        900
    );
}

function applyFilters() {
    if (!state.graphData) return;
    const rawNodes = (state.graphData.elements.nodes || []).map(n => n.data);
    const rawLinks = (state.graphData.elements.edges || []).map(e => e.data);

    const visibleNodes = rawNodes.filter(n => state.filters[n.category || 'code']);
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));
    const visibleLinks = rawLinks.filter(l => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));

    if (state.graph3d) {
        state.graph3d.graphData({
            nodes: visibleNodes,
            links: visibleLinks
        });
    }
}

// ==========================================================================
// Node Selection & Context Inspector
// ==========================================================================

function selectNode(data) {
    if (!data) return;
    state.selectedNode = data;

    if (state.graph3d) {
        const gNodes = state.graph3d.graphData().nodes;
        const targetNode = gNodes.find(n => n.id === data.id);
        const gLinks = state.graph3d.graphData().links;

        const neighbors = new Set([data.id]);
        gLinks.forEach(link => {
            const s = typeof link.source === 'object' ? link.source.id : link.source;
            const t = typeof link.target === 'object' ? link.target.id : link.target;
            if (s === data.id) {
                neighbors.add(t);
                link.__highlight = true;
            } else if (t === data.id) {
                neighbors.add(s);
                link.__highlight = true;
            } else {
                link.__highlight = false;
            }
        });

        state.highlightNodes = neighbors;
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());

        if (targetNode) flyToNode(targetNode);
    }

    showContextPanel(data);
}

function clearSelection() {
    state.selectedNode = null;
    state.highlightNodes.clear();

    if (state.graph3d) {
        state.graph3d.graphData().links.forEach(l => { l.__highlight = false; });
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
    }

    els.contextPanel.classList.add('closed');
}

function handleShiftClick(data) {
    if (!state.traceSource) {
        state.traceSource = data.id;
        els.commandBar.placeholder = `Select target destination node for trace from ${data.label || data.id}...`;
    } else if (state.traceSource !== data.id) {
        runTrace(state.traceSource, data.id);
        state.traceSource = null;
    }
}

function showContextPanel(data) {
    closeAllPopovers();
    els.contextPanel.classList.remove('closed');

    const label = data.label || data.id;
    els.nodeLabel.textContent = label;
    els.nodeCategory.textContent = data.category || 'code';
    els.nodeTypeBadge.textContent = data.file_type || (data.is_class ? 'class' : (data.is_callable ? 'callable' : 'symbol'));

    els.nodeSource.textContent = (data.source_file || '') + (data.source_location ? `:${data.source_location}` : '');
    els.nodeCommunity.textContent = data.community != null ? `Cluster ${data.community}` : 'None';
    els.nodeDegree.textContent = data.degree || 0;

    // Build connections list grouped by relation
    els.nodeConnections.innerHTML = '';
    const grouped = {};
    if (state.graphData && state.graphData.elements.edges) {
        state.graphData.elements.edges.forEach(edge => {
            const e = edge.data;
            const sId = typeof e.source === 'object' ? e.source.id : e.source;
            const tId = typeof e.target === 'object' ? e.target.id : e.target;
            if (sId === data.id) {
                const rel = e.relation || 'out';
                if (!grouped[rel]) grouped[rel] = [];
                grouped[rel].push(tId);
            } else if (tId === data.id) {
                const rel = `in (${e.relation || 'ref'})`;
                if (!grouped[rel]) grouped[rel] = [];
                grouped[rel].push(sId);
            }
        });
    }

    if (Object.keys(grouped).length === 0) {
        els.nodeConnections.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">No direct connections recorded.</div>';
    } else {
        for (const [rel, nodeIds] of Object.entries(grouped)) {
            const groupDiv = document.createElement('div');
            groupDiv.className = 'conn-group';
            const header = document.createElement('div');
            header.className = 'conn-group-header';
            header.textContent = `${rel} (${nodeIds.length})`;
            groupDiv.appendChild(header);

            const chipsDiv = document.createElement('div');
            chipsDiv.className = 'conn-chips';

            nodeIds.slice(0, 16).forEach(tid => {
                const a = document.createElement('a');
                a.className = 'symbol-link';
                let friendly = tid;
                if (state.graphData) {
                    const found = state.graphData.elements.nodes.find(n => n.data.id === tid);
                    if (found && found.data.label) friendly = found.data.label;
                }
                a.textContent = friendly;
                a.onclick = () => selectNodeByLabel(friendly);
                chipsDiv.appendChild(a);
            });

            groupDiv.appendChild(chipsDiv);
            els.nodeConnections.appendChild(groupDiv);
        }
    }
}

function selectNodeByLabel(label) {
    if (!state.graphData) return;
    const cleanLabel = (label || '').toLowerCase().trim();
    const found = state.graphData.elements.nodes.find(n => {
        const l = (n.data.label || '').toLowerCase();
        const id = (n.data.id || '').toLowerCase();
        return l === cleanLabel || id === cleanLabel;
    });

    if (found) {
        selectNode(found.data);
    }
}

window.selectNodeByLabel = selectNodeByLabel;

// ==========================================================================
// Command Bar Routing (Search / Query / Impact / Trace)
// ==========================================================================

function handleCommandSubmit(input) {
    if (!input) return;

    // Detect mode
    const activeBadge = document.querySelector('.mode-badge.active');
    const explicitMode = activeBadge ? activeBadge.dataset.mode : 'auto';

    if (explicitMode === 'trace' || input.includes('->') || input.includes('→')) {
        const parts = input.split(/->|→/).map(s => s.trim());
        if (parts.length >= 2) {
            runTrace(parts[0], parts[1]);
            return;
        }
    }

    if (explicitMode === 'impact') {
        runImpact(input);
        return;
    }

    if (explicitMode === 'query') {
        runQuery(input);
        return;
    }

    // Auto Mode: check if matches node exactly or fuzzy
    if (state.graphData) {
        const match = state.graphData.elements.nodes.find(n => {
            const l = (n.data.label || '').toLowerCase();
            const id = (n.data.id || '').toLowerCase();
            return l === input.toLowerCase() || id === input.toLowerCase();
        });
        if (match) {
            selectNode(match.data);
            return;
        }
    }

    // If identifier-like without spaces, default to impact
    if (/^[a-zA-Z_][a-zA-Z0-9_.]*$/.test(input) && !input.includes(' ')) {
        runImpact(input);
    } else {
        runQuery(input);
    }
}

// ==========================================================================
// Analysis Workflows: Query, Impact, Trace
// ==========================================================================

function clearOverlays() {
    if (state.graph3d) {
        const data = state.graph3d.graphData();
        data.nodes.forEach(n => {
            n.__impactTarget = false;
            n.__impacted = false;
            n.__tracePath = false;
        });
        data.links.forEach(l => {
            l.__impact = false;
            l.__trace = false;
        });
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());
    }
    els.clearOverlaysBtn.classList.add('hidden');
}

async function runQuery(query) {
    if (state.inFlight) return;
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Synthesizing multi-tier architecture context for: <strong>${escapeHtml(query)}</strong>...</div>`);

    try {
        const payload = {
            project_path: state.currentProject,
            query: query,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/query', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        addOperationHistory('query', query);
        renderOperationResults(res.synthesized_context || 'No response generated.');
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Query Error: ${escapeHtml(e.message)}</div>`);
    } finally {
        setBusy(false);
    }
}

async function runImpact(symbol) {
    if (state.inFlight) return;
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Calculating blast radius for <strong>${escapeHtml(symbol)}</strong>...</div>`);

    try {
        const payload = {
            project_path: state.currentProject,
            symbol: symbol,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/impact', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        addOperationHistory('impact', symbol);
        applyImpactOverlay(symbol, res);
        renderOperationResults(res.synthesized_report || 'No impact report generated.');
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Impact Error: ${escapeHtml(e.message)}</div>`);
    } finally {
        setBusy(false);
    }
}

function applyImpactOverlay(symbol, report) {
    clearOverlays();
    els.clearOverlaysBtn.classList.remove('hidden');

    const affectedSymbols = new Set([symbol.toLowerCase()]);
    if (report.call_hierarchy && Array.isArray(report.call_hierarchy)) {
        report.call_hierarchy.forEach(item => {
            if (item.symbol) affectedSymbols.add(item.symbol.toLowerCase());
        });
    }

    if (state.graph3d) {
        const gData = state.graph3d.graphData();
        gData.nodes.forEach(n => {
            const l = (n.label || '').toLowerCase();
            const id = (n.id || '').toLowerCase();
            if (l === symbol.toLowerCase() || id === symbol.toLowerCase()) {
                n.__impactTarget = true;
            } else if (affectedSymbols.has(l) || affectedSymbols.has(id)) {
                n.__impacted = true;
            }
        });

        gData.links.forEach(l => {
            const s = typeof l.source === 'object' ? l.source.label || l.source.id : l.source;
            const t = typeof l.target === 'object' ? l.target.label || l.target.id : l.target;
            if (affectedSymbols.has(String(s).toLowerCase()) && affectedSymbols.has(String(t).toLowerCase())) {
                l.__impact = true;
            }
        });

        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());
    }
}

async function runTrace(fromSym, toSym) {
    if (state.inFlight) return;
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Tracing execution path: <strong>${escapeHtml(fromSym)} &rarr; ${escapeHtml(toSym)}</strong>...</div>`);

    try {
        const payload = {
            project_path: state.currentProject,
            from_symbol: fromSym,
            to_symbol: toSym,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/trace', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        addOperationHistory('trace', `${fromSym} -> ${toSym}`);
        applyTraceOverlay(res);
        renderOperationResults(res.synthesized_flow || 'No path found.');
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Trace Error: ${escapeHtml(e.message)}</div>`);
    } finally {
        setBusy(false);
    }
}

function applyTraceOverlay(traceRes) {
    clearOverlays();
    els.clearOverlaysBtn.classList.remove('hidden');

    if (!traceRes.path_found || !traceRes.steps) return;

    const pathSymbols = new Set(traceRes.steps.map(s => (s.symbol || s).toLowerCase()));

    if (state.graph3d) {
        const gData = state.graph3d.graphData();
        gData.nodes.forEach(n => {
            const l = (n.label || '').toLowerCase();
            const id = (n.id || '').toLowerCase();
            if (pathSymbols.has(l) || pathSymbols.has(id)) {
                n.__tracePath = true;
            }
        });

        gData.links.forEach(l => {
            const s = typeof l.source === 'object' ? l.source.label || l.source.id : l.source;
            const t = typeof l.target === 'object' ? l.target.label || l.target.id : l.target;
            if (pathSymbols.has(String(s).toLowerCase()) && pathSymbols.has(String(t).toLowerCase())) {
                l.__trace = true;
            }
        });

        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());
    }
}

function renderOperationResults(markdown) {
    state.lastResults = markdown;
    if (els.copyResultsBtn) els.copyResultsBtn.classList.remove('hidden');

    let html = '';
    if (window.marked) {
        html = marked.parse(markdown);
    } else {
        html = `<pre>${escapeHtml(markdown)}</pre>`;
    }

    setSafeHtml(els.resultsOutput, html);

    // Cross-link symbols in markdown
    linkifySymbolsInOutput(els.resultsOutput);

    // Render Mermaid diagrams if present
    if (window.mermaid) {
        const codeBlocks = els.resultsOutput.querySelectorAll('pre code.language-mermaid, pre code.language-flowchart');
        codeBlocks.forEach((block, index) => {
            const container = block.parentElement;
            const id = `mermaid-chart-${Date.now()}-${index}`;
            const graphDef = block.textContent;
            try {
                mermaid.render(id, graphDef).then(({ svg }) => {
                    container.innerHTML = svg;
                });
            } catch (err) {
                console.error('Mermaid render error:', err);
            }
        });
    }
}

// ==========================================================================
// 3-Tier Indexing Engine (SSE Stream)
// ==========================================================================

async function runIndexing() {
    if (state.inFlight) return;
    persistUiTokenFromInput();
    const force = els.forceIndex ? els.forceIndex.checked : false;
    const multi = els.multimodalIndex ? els.multimodalIndex.checked : false;

    setBusy(true);
    openDrawer();
    switchDrawerTab('terminal');
    els.terminalOutput.textContent = `[CKC Engine] Initiating 3-Tier Indexing for ${state.currentProject}...\n`;

    if (els.cancelIndexBtn) els.cancelIndexBtn.classList.remove('hidden');
    if (els.runIndexBtn) els.runIndexBtn.classList.add('hidden');

    const params = new URLSearchParams({
        project: state.currentProject,
        force: String(force),
        multimodal: String(multi)
    });
    if (state.uiToken) {
        params.append('token', state.uiToken);
    }

    const sseUrl = `/api/index/stream?${params.toString()}`;
    const evtSource = new EventSource(sseUrl);
    state.indexingAbort = evtSource;

    evtSource.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            handleIndexingEvent(data);
        } catch (_) {
            els.terminalOutput.textContent += `${e.data}\n`;
            els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
        }
    };

    evtSource.onerror = (e) => {
        console.error('SSE Error:', e);
        evtSource.close();
        finishIndexing(false, 'Indexing connection interrupted or failed.');
    };
}

function handleIndexingEvent(data) {
    const text = data.message || data.log || JSON.stringify(data);
    els.terminalOutput.textContent += `${text}\n`;
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;

    if (data.event === 'complete' || data.type === 'complete') {
        finishIndexing(true, 'Indexing completed successfully.');
    } else if (data.event === 'error' || data.type === 'error') {
        finishIndexing(false, data.message || 'Indexing error occurred.');
    }
}

function finishIndexing(success, msg) {
    if (state.indexingAbort) {
        state.indexingAbort.close();
        state.indexingAbort = null;
    }
    if (els.cancelIndexBtn) els.cancelIndexBtn.classList.add('hidden');
    if (els.runIndexBtn) els.runIndexBtn.classList.remove('hidden');
    setBusy(false);

    els.terminalOutput.textContent += `\n[CKC Engine] ${msg}\n`;
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;

    if (success) {
        loadProject();
    }
}

async function cancelIndexing() {
    if (!state.currentProject) return;
    try {
        await apiFetch('/api/index/cancel', {
            method: 'POST',
            body: JSON.stringify({ project_path: state.currentProject })
        });
        finishIndexing(false, 'Indexing cancelled by user.');
    } catch (e) {
        console.error('Failed to cancel indexing:', e);
    }
}

// ==========================================================================
// Bottom Drawer Management
// ==========================================================================

function openDrawer() {
    state.drawerOpen = true;
    els.drawer.classList.add('open');
}

function closeDrawer() {
    state.drawerOpen = false;
    els.drawer.classList.remove('open');
}

function toggleDrawer() {
    state.drawerOpen = !state.drawerOpen;
    els.drawer.classList.toggle('open', state.drawerOpen);
}

function switchDrawerTab(tab) {
    state.drawerTab = tab;
    els.tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });

    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    const activePane = document.getElementById(`pane-${tab}`);
    if (activePane) activePane.classList.add('active');
}

// ==========================================================================
// Samples & History
// ==========================================================================

async function loadSamples() {
    try {
        const res = await apiFetch('/api/samples');
        if (res.samples && Array.isArray(res.samples)) {
            els.samplePicker.innerHTML = '<option value="">Choose a bundled sample…</option>';
            res.samples.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.path;
                opt.textContent = `${s.name} (${s.id})`;
                els.samplePicker.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Failed to load samples:', e);
    }
}

function addOperationHistory(type, param) {
    if (!els.opsHistory) return;
    const chip = document.createElement('span');
    chip.className = 'op-chip';
    chip.textContent = `${type}: ${param}`;
    chip.addEventListener('click', () => {
        if (type === 'impact') runImpact(param);
        else if (type === 'query') runQuery(param);
    });

    if (els.opsHistory.firstChild) {
        els.opsHistory.insertBefore(chip, els.opsHistory.firstChild);
    } else {
        els.opsHistory.appendChild(chip);
    }

    while (els.opsHistory.children.length > 5) {
        els.opsHistory.removeChild(els.opsHistory.lastChild);
    }
}

function linkifySymbolsInOutput(container) {
    if (!state.graphData || !state.graphData.elements.nodes) return;
    const labelSet = new Set();
    state.graphData.elements.nodes.forEach(n => {
        if (n.data.label && n.data.label.length >= 3) {
            labelSet.add(n.data.label);
        }
    });

    const sortedLabels = Array.from(labelSet).sort((a, b) => b.length - a.length).slice(0, 100);

    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    const nodesToReplace = [];
    let node;
    while ((node = walker.nextNode())) {
        if (node.parentElement && (node.parentElement.tagName === 'A' || node.parentElement.tagName === 'PRE' || node.parentElement.tagName === 'CODE')) {
            continue;
        }
        nodesToReplace.push(node);
    }

    nodesToReplace.forEach(textNode => {
        let content = textNode.textContent;
        let modified = false;

        for (const label of sortedLabels) {
            if (content.includes(label)) {
                const regex = new RegExp(`\\b(${label})\\b`, 'g');
                if (regex.test(content)) {
                    content = content.replace(regex, `###SYM###$1###/SYM###`);
                    modified = true;
                }
            }
        }

        if (modified) {
            const span = document.createElement('span');
            span.innerHTML = content
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/###SYM###(.*?)###\/SYM###/g, '<a class="symbol-link" onclick="selectNodeByLabel(\'$1\')">$1</a>');
            textNode.parentNode.replaceChild(span, textNode);
        }
    });
}

// Start application
document.addEventListener('DOMContentLoaded', init);
