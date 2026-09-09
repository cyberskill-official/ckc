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
    isTraceMode: false,
    graphData: null,
    communities: [],
    filters: { code: true, doc: true, schema: true, test: true },
    isAutoRotating: false,
    indexingAbort: null,
    queryAbort: null,
    inFlight: false,
    drawerOpen: false,
    drawerTab: 'terminal',
    lastResults: '',
    highlightNodes: new Set(),
    highlightLinks: new Set(),
    hoverNode: null,
    searchMode: 'auto',
    searchSelectedIndex: -1,
    currentMatches: [],
    palette: [
        '#38bdf8', '#818cf8', '#c084fc', '#f472b6', '#fb7185',
        '#f59e0b', '#10b981', '#34d399', '#2dd4bf', '#22d3ee',
        '#a78bfa', '#e879f9', '#fb923c', '#4ade80', '#60a5fa', '#94a3b8'
    ]
};

// Expose state globally for DevTools inspection & automated tests
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

    // Spotlight Command Bar & Search Palette
    commandBar: document.getElementById('command-bar'),
    commandClearBtn: document.getElementById('command-clear-btn'),
    searchModeBtn: document.getElementById('search-mode-btn'),
    currentModeLabel: document.getElementById('current-mode-label'),
    searchModeDropdown: document.getElementById('search-mode-dropdown'),
    searchResultsDropdown: document.getElementById('search-results-dropdown'),
    searchResultsList: document.getElementById('search-results-list'),
    searchActionsBar: document.getElementById('search-actions-bar'),

    // Trace Mode Banner
    traceModeBanner: document.getElementById('trace-mode-banner'),
    traceSourceName: document.getElementById('trace-source-name'),
    traceCancelBtn: document.getElementById('trace-cancel-btn'),

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
    clearOverlaysBtn: document.getElementById('clear-overlays-btn'),

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
    copySourcePathBtn: document.getElementById('copy-source-path-btn'),
    actionImpact: document.getElementById('action-impact'),
    actionTrace: document.getElementById('action-trace'),
    actionQuery: document.getElementById('action-query'),

    // Bottom Drawer
    drawer: document.getElementById('drawer'),
    drawerToggle: document.getElementById('drawer-toggle'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    terminalOutput: document.getElementById('terminal-output'),
    resultsOutput: document.getElementById('results-output'),
    copyResultsBtn: document.getElementById('copy-results-btn'),

    // Toasts
    toastContainer: document.getElementById('toast-container')
};

// ==========================================================================
// Toast Notification Helper
// ==========================================================================

function showToast(message, type = 'info') {
    if (!els.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    let icon = '';
    if (type === 'success') {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
    els.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => { toast.remove(); }, 200);
    }, 3000);
}

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
    } else {
        showWelcomeOverlay();
    }
}

function showWelcomeOverlay() {
    const container = els.container3d || document.getElementById('graph-3d');
    if (!container || document.getElementById('welcome-overlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'welcome-overlay';
    overlay.innerHTML = DOMPurify.sanitize(`
        <div class="welcome-card">
            <h1 class="welcome-title">CKC</h1>
            <p class="welcome-subtitle">3D Code Knowledge Explorer</p>
            <div class="welcome-steps">
                <div class="welcome-step"><span class="step-num">1</span> Enter a project path or pick a sample</div>
                <div class="welcome-step"><span class="step-num">2</span> Click any node to inspect it</div>
                <div class="welcome-step"><span class="step-num">3</span> Search, query, trace, or analyze impact</div>
            </div>
            <div class="welcome-actions">
                <button class="btn-welcome-sample" id="welcome-open-btn">Open a Project</button>
            </div>
            <p class="welcome-shortcut">Press <kbd>/</kbd> to search · <kbd>P</kbd> to switch projects</p>
        </div>
    `);
    container.appendChild(overlay);
    const openBtn = document.getElementById('welcome-open-btn');
    if (openBtn) {
        openBtn.addEventListener('click', () => {
            if (els.projectPillBtn) els.projectPillBtn.click();
            overlay.remove();
        });
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
    if (els.searchModeDropdown) els.searchModeDropdown.classList.add('closed');
    if (els.searchResultsDropdown) els.searchResultsDropdown.classList.add('closed');
    // Update ARIA expanded state on trigger buttons
    if (els.projectPillBtn) els.projectPillBtn.setAttribute('aria-expanded', 'false');
    if (els.layersToggleBtn) els.layersToggleBtn.setAttribute('aria-expanded', 'false');
    if (els.headerIndexBtn) els.headerIndexBtn.setAttribute('aria-expanded', 'false');
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
    if (els.loadBtn) {
        els.loadBtn.disabled = busy;
        const spinner = els.loadBtn.querySelector('.btn-spinner');
        const icon = els.loadBtn.querySelector('.btn-icon-load');
        const text = els.loadBtn.querySelector('span');
        if (spinner) spinner.classList.toggle('hidden', !busy);
        if (icon) icon.classList.toggle('hidden', busy);
        if (text) text.textContent = busy ? 'Loading...' : 'Load Project';
    }
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
            if (state.isTraceMode && state.traceSource) {
                if (state.traceSource !== node.id) {
                    runTrace(state.traceSource, node.id);
                    exitTraceMode();
                }
                return;
            }

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
            if (state.isTraceMode) {
                exitTraceMode();
            } else {
                clearSelection();
                clearOverlays();
            }
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
            if (!isOpen) {
                els.projectPopover.classList.remove('closed');
                els.projectPillBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (els.closeProjectPopoverBtn) {
        els.closeProjectPopoverBtn.addEventListener('click', () => {
            if (els.projectPopover) els.projectPopover.classList.add('closed');
            if (els.projectPillBtn) els.projectPillBtn.setAttribute('aria-expanded', 'false');
        });
    }

    if (els.layersToggleBtn && els.layersPopover) {
        els.layersToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.layersPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) {
                els.layersPopover.classList.remove('closed');
                els.layersToggleBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (els.closeLayersPopoverBtn) {
        els.closeLayersPopoverBtn.addEventListener('click', () => {
            if (els.layersPopover) els.layersPopover.classList.add('closed');
            if (els.layersToggleBtn) els.layersToggleBtn.setAttribute('aria-expanded', 'false');
        });
    }

    if (els.headerIndexBtn && els.indexPopover) {
        els.headerIndexBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) {
                els.indexPopover.classList.remove('closed');
                els.headerIndexBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (els.readyBadge && els.indexPopover) {
        els.readyBadge.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) {
                els.indexPopover.classList.remove('closed');
                if (els.headerIndexBtn) els.headerIndexBtn.setAttribute('aria-expanded', 'true');
            }
        });
    }
    if (els.closeIndexPopoverBtn) {
        els.closeIndexPopoverBtn.addEventListener('click', () => {
            if (els.indexPopover) els.indexPopover.classList.add('closed');
            if (els.headerIndexBtn) els.headerIndexBtn.setAttribute('aria-expanded', 'false');
        });
    }

    // Search Mode Button & Dropdown
    if (els.searchModeBtn && els.searchModeDropdown) {
        els.searchModeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.searchModeDropdown.classList.contains('closed');
            closeAllPopovers();
            if (!isOpen) els.searchModeDropdown.classList.remove('closed');
        });

        els.searchModeDropdown.querySelectorAll('.mode-option').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const mode = opt.dataset.mode;
                setSearchMode(mode);
                els.searchModeDropdown.classList.add('closed');
                els.commandBar.focus();
            });
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
        const inSearchMode = els.searchModeBtn && els.searchModeBtn.contains(e.target);
        const inSearchDropdown = els.searchResultsDropdown && els.searchResultsDropdown.contains(e.target);
        const inCommandBar = els.commandBar && els.commandBar.contains(e.target);

        if (!inProject && !inLayers && !inIndex && !inPill && !inLayersBtn && !inIndexBtn && !inReadyBadge && !inSearchMode && !inSearchDropdown && !inCommandBar) {
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

    // Live Search Input Handler
    els.commandBar.addEventListener('input', () => {
        const val = els.commandBar.value.trim();
        if (els.commandClearBtn) {
            els.commandClearBtn.classList.toggle('hidden', val.length === 0);
        }
        handleLiveSearch(val);
    });

    if (els.commandClearBtn) {
        els.commandClearBtn.addEventListener('click', () => {
            els.commandBar.value = '';
            els.commandClearBtn.classList.add('hidden');
            if (els.searchResultsDropdown) els.searchResultsDropdown.classList.add('closed');
            els.commandBar.focus();
        });
    }

    // Command Bar Keyboard Navigation
    els.commandBar.addEventListener('keydown', (e) => {
        const isDropdownOpen = els.searchResultsDropdown && !els.searchResultsDropdown.classList.contains('closed');

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (isDropdownOpen) navigateSearchResults(1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (isDropdownOpen) navigateSearchResults(-1);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (isDropdownOpen && state.searchSelectedIndex >= 0) {
                executeSelectedSearchResult();
            } else {
                handleCommandSubmit(els.commandBar.value.trim());
            }
        } else if (e.key === 'Escape') {
            if (isDropdownOpen) {
                e.preventDefault();
                els.searchResultsDropdown.classList.add('closed');
            }
        }
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
            enterTraceMode(state.selectedNode);
        }
    });

    if (els.traceCancelBtn) {
        els.traceCancelBtn.addEventListener('click', exitTraceMode);
    }

    els.actionQuery.addEventListener('click', () => {
        if (state.selectedNode) runQuery(`Explain the purpose and architecture of ${state.selectedNode.label || state.selectedNode.id}`);
    });

    if (els.copySymbolNameBtn) {
        els.copySymbolNameBtn.addEventListener('click', () => {
            if (state.selectedNode) {
                const sym = state.selectedNode.label || state.selectedNode.id;
                navigator.clipboard.writeText(sym);
                showToast(`Copied "${sym}" to clipboard`, 'success');
            }
        });
    }

    if (els.copySourcePathBtn) {
        els.copySourcePathBtn.addEventListener('click', () => {
            if (state.selectedNode) {
                const src = (state.selectedNode.source_file || '') + (state.selectedNode.source_location ? `:${state.selectedNode.source_location}` : '');
                if (src) {
                    navigator.clipboard.writeText(src);
                    showToast(`Copied source path to clipboard`, 'success');
                }
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
            showToast('Analysis Dossier copied to clipboard', 'success');
        }
    });

    els.clearOverlaysBtn.addEventListener('click', clearOverlays);

    // Global Hotkeys
    document.addEventListener('keydown', (e) => {
        const isInput = document.activeElement && (document.activeElement.tagName === 'INPUT' || document.activeElement.tagName === 'TEXTAREA' || document.activeElement.tagName === 'SELECT');

        if (e.key === 'Escape') {
            if (state.isTraceMode) {
                exitTraceMode();
            } else {
                closeAllPopovers();
                clearSelection();
                clearOverlays();
                els.contextPanel.classList.add('closed');
            }
        } else if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && !isInput) {
            e.preventDefault();
            els.commandBar.focus();
            els.commandBar.select();
        } else if (e.key === 'f' && !isInput) {
            fitGraphView();
        } else if (e.key === 'r' && !isInput) {
            resetCameraView();
        } else if (e.key === ' ' && !isInput) {
            e.preventDefault();
            if (els.autoRotateBtn) els.autoRotateBtn.click();
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
// Trace Mode Workflow
// ==========================================================================

function enterTraceMode(sourceNode) {
    state.traceSource = sourceNode.id;
    state.isTraceMode = true;
    const name = sourceNode.label || sourceNode.id;
    if (els.traceSourceName) els.traceSourceName.textContent = name;
    if (els.traceModeBanner) els.traceModeBanner.classList.remove('hidden');
    showToast(`Trace Mode Active: Click destination node in 3D to trace path from ${name}`, 'info');
}

function exitTraceMode() {
    state.isTraceMode = false;
    state.traceSource = null;
    if (els.traceModeBanner) els.traceModeBanner.classList.add('hidden');
}

// ==========================================================================
// Search Mode & Live Autocomplete Palette
// ==========================================================================

function setSearchMode(mode) {
    state.searchMode = mode;
    if (els.currentModeLabel) {
        els.currentModeLabel.textContent = mode.charAt(0).toUpperCase() + mode.slice(1);
    }
    if (els.searchModeDropdown) {
        els.searchModeDropdown.querySelectorAll('.mode-option').forEach(opt => {
            opt.classList.toggle('active', opt.dataset.mode === mode);
        });
    }

    if (mode === 'query') {
        els.commandBar.placeholder = 'Ask a question about codebase architecture...';
    } else if (mode === 'impact') {
        els.commandBar.placeholder = 'Enter symbol for blast radius analysis (e.g. AuthService)...';
    } else if (mode === 'trace') {
        els.commandBar.placeholder = 'Enter flow trace: symbolA -> symbolB...';
    } else {
        els.commandBar.placeholder = 'Search symbols, ask questions, or "A -> B" to trace...';
    }
}

function handleLiveSearch(query) {
    if (!els.searchResultsDropdown || !els.searchResultsList) return;

    if (!query || query.length < 1) {
        els.searchResultsDropdown.classList.add('closed');
        state.currentMatches = [];
        state.searchSelectedIndex = -1;
        return;
    }

    const q = query.toLowerCase().trim();
    const rawNodes = state.graphData ? (state.graphData.elements.nodes || []).map(n => n.data) : [];

    // Filter nodes with relevance scoring
    const matches = [];
    rawNodes.forEach(node => {
        const label = (node.label || '').toLowerCase();
        const id = (node.id || '').toLowerCase();
        const src = (node.source_file || '').toLowerCase();

        let score = 0;
        if (label === q || id === q) score += 100;
        else if (label.startsWith(q)) score += 50;
        else if (label.includes(q)) score += 25;
        else if (src.includes(q)) score += 10;
        else if (id.includes(q)) score += 5;

        if (score > 0) {
            matches.push({ node, score });
        }
    });

    matches.sort((a, b) => b.score - a.score || (b.node.degree || 0) - (a.node.degree || 0));
    state.currentMatches = matches.slice(0, 12).map(m => m.node);
    state.searchSelectedIndex = state.currentMatches.length > 0 ? 0 : -1;

    renderSearchResults(query, state.currentMatches);
    els.searchResultsDropdown.classList.remove('closed');
}

function renderSearchResults(query, matches) {
    els.searchResultsList.innerHTML = '';

    if (matches.length === 0) {
        els.searchResultsList.innerHTML = `<div class="search-empty">No matching symbols found for "<strong>${escapeHtml(query)}</strong>"</div>`;
    } else {
        matches.forEach((node, idx) => {
            const item = document.createElement('div');
            item.className = `search-result-item ${idx === state.searchSelectedIndex ? 'selected' : ''}`;
            const cat = node.category || 'code';
            const colorClass = `color-${cat}`;
            const srcLoc = (node.source_file || '') + (node.source_location ? `:${node.source_location}` : '');

            item.innerHTML = `
                <span class="search-item-shape ${colorClass}"></span>
                <div class="search-item-info">
                    <span class="search-item-label">${escapeHtml(node.label || node.id)}</span>
                    <span class="search-item-path">${escapeHtml(srcLoc)}</span>
                </div>
                <span class="search-item-meta">${node.degree || 0} deg</span>
            `;

            item.addEventListener('click', () => {
                selectNode(node);
                closeAllPopovers();
            });

            els.searchResultsList.appendChild(item);
        });
    }

    // Quick Actions
    els.searchActionsBar.innerHTML = '';

    const actionImpact = document.createElement('div');
    actionImpact.className = 'search-action-btn';
    actionImpact.innerHTML = `
        <svg class="search-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
        <span>Analyze Blast Radius for <strong>"${escapeHtml(query)}"</strong></span>
    `;
    actionImpact.addEventListener('click', () => {
        closeAllPopovers();
        runImpact(query);
    });
    els.searchActionsBar.appendChild(actionImpact);

    const actionQuery = document.createElement('div');
    actionQuery.className = 'search-action-btn';
    actionQuery.innerHTML = `
        <svg class="search-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <span>Query Architecture: <strong>"${escapeHtml(query)}"</strong></span>
    `;
    actionQuery.addEventListener('click', () => {
        closeAllPopovers();
        runQuery(query);
    });
    els.searchActionsBar.appendChild(actionQuery);
}

function navigateSearchResults(dir) {
    const total = state.currentMatches.length;
    if (total === 0) return;

    state.searchSelectedIndex = (state.searchSelectedIndex + dir + total) % total;

    const items = els.searchResultsList.querySelectorAll('.search-result-item');
    items.forEach((item, idx) => {
        item.classList.toggle('selected', idx === state.searchSelectedIndex);
        if (idx === state.searchSelectedIndex) {
            item.scrollIntoView({ block: 'nearest' });
        }
    });
}

function executeSelectedSearchResult() {
    if (state.searchSelectedIndex >= 0 && state.currentMatches[state.searchSelectedIndex]) {
        const node = state.currentMatches[state.searchSelectedIndex];
        selectNode(node);
        closeAllPopovers();
    }
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

    // Clear stale analysis results from previous project
    if (els.resultsOutput) els.resultsOutput.innerHTML = '';
    state.lastResults = null;
    document.getElementById('welcome-overlay')?.remove();
    document.getElementById('graph-legend')?.classList.remove('hidden');

    persistUiTokenFromInput();
    setBusy(true);
    try {
        const [statusRes, graphRes] = await Promise.all([
            apiFetch(`/api/status?project=${encodeURIComponent(state.currentProject)}`),
            apiFetch(`/api/graph?project=${encodeURIComponent(state.currentProject)}`),
        ]);

        updateStatus(statusRes);
        renderGraph(graphRes);
        showToast(`Loaded ${state.currentProjectLabel ? state.currentProjectLabel.textContent : 'project'} (${graphRes.meta?.node_count || 0} symbols)`, 'success');
    } catch (e) {
        console.error('Failed to load project:', e);
        els.readyBadge.className = 'badge-status badge-error';
        if (els.readyBadgeText) els.readyBadgeText.textContent = 'Error';
        showToast(`Failed to load project: ${e.message}`, 'error');
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
        const model = res.llm.model || 'Active';
        const shortModel = model.length > 16 ? model.slice(0, 14) + '…' : model;
        els.llmChip.textContent = `LLM: ${shortModel}`;
        els.llmChip.title = `Model: ${model} (${res.llm.base_url || 'local'})`;
        els.llmChip.className = 'badge-chip badge-ready';
    } else {
        els.llmChip.textContent = 'LLM: Off';
        els.llmChip.title = 'LLM synthesis is not configured';
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

    // Sanitize link sources/targets to prevent d3-force object mutation breakage
    const visibleNodes = rawNodes.filter(n => state.filters[n.category || 'code']);
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

    const cleanLinks = rawLinks.map(l => {
        const sId = typeof l.source === 'object' ? l.source.id : l.source;
        const tId = typeof l.target === 'object' ? l.target.id : l.target;
        return Object.assign({}, l, { source: sId, target: tId });
    }).filter(l => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));

    if (state.graph3d) {
        state.graph3d.graphData({
            nodes: visibleNodes,
            links: cleanLinks
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

    const cleanLinks = rawLinks.map(l => {
        const sId = typeof l.source === 'object' ? l.source.id : l.source;
        const tId = typeof l.target === 'object' ? l.target.id : l.target;
        return Object.assign({}, l, { source: sId, target: tId });
    }).filter(l => visibleNodeIds.has(l.source) && visibleNodeIds.has(l.target));

    if (state.graph3d) {
        state.graph3d.graphData({
            nodes: visibleNodes,
            links: cleanLinks
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
        enterTraceMode(data);
    } else if (state.traceSource !== data.id) {
        runTrace(state.traceSource, data.id);
        exitTraceMode();
    }
}

function showContextPanel(data) {
    closeAllPopovers();
    els.contextPanel.classList.remove('closed');

    const label = data.label || data.id;
    els.nodeLabel.textContent = label;
    const cat = (data.category || 'code').toLowerCase();
    els.nodeCategory.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);

    let typeLabel = 'Symbol';
    if (data.is_class) {
        typeLabel = 'Class';
    } else if (data.is_callable) {
        typeLabel = 'Callable';
    } else if (data.file_type && data.file_type.toLowerCase() !== cat) {
        typeLabel = data.file_type.charAt(0).toUpperCase() + data.file_type.slice(1);
    } else if (data.id && (data.id.endsWith('.py') || data.id.endsWith('.ts') || data.id.endsWith('.js') || data.id.endsWith('.json'))) {
        typeLabel = 'Module';
    }
    els.nodeTypeBadge.textContent = typeLabel;

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
    closeAllPopovers();

    const mode = state.searchMode;

    if (mode === 'trace' || input.includes('->') || input.includes('→')) {
        const parts = input.split(/->|→/).map(s => s.trim());
        if (parts.length >= 2) {
            runTrace(parts[0], parts[1]);
            return;
        }
    }

    if (mode === 'impact') {
        runImpact(input);
        return;
    }

    if (mode === 'query') {
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
    if (state.queryAbort) state.queryAbort.abort();
    state.queryAbort = new AbortController();
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);"><svg class="btn-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:8px;"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle></svg>Synthesizing multi-tier architecture context for: <strong>${escapeHtml(query)}</strong>...<button id="cancel-query-btn" style="margin-left:12px;padding:4px 12px;border-radius:6px;border:1px solid var(--border-subtle);background:var(--bg-card);color:var(--text-secondary);cursor:pointer;font-size:12px;">Cancel</button></div>`);
    const cancelBtn = document.getElementById('cancel-query-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', () => { if (state.queryAbort) state.queryAbort.abort(); });

    try {
        const payload = {
            project_path: state.currentProject,
            query: query,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/query', {
            method: 'POST',
            body: JSON.stringify(payload),
            signal: state.queryAbort.signal
        });

        addOperationHistory('query', query);
        renderOperationResults(res.synthesized_context || 'No response generated.');
        showToast(`Query completed for "${query}"`, 'success');
    } catch (e) {
        if (e.name === 'AbortError') {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Query cancelled.</div>`);
            showToast('Query cancelled', 'info');
        } else {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Query Error: ${escapeHtml(e.message)}</div>`);
            showToast(`Query failed: ${e.message}`, 'error');
        }
    } finally {
        state.queryAbort = null;
        setBusy(false);
    }
}

async function runImpact(symbol) {
    if (state.inFlight) return;
    if (state.queryAbort) state.queryAbort.abort();
    state.queryAbort = new AbortController();
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);"><svg class="btn-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:8px;"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle></svg>Calculating blast radius for <strong>${escapeHtml(symbol)}</strong>...<button id="cancel-query-btn" style="margin-left:12px;padding:4px 12px;border-radius:6px;border:1px solid var(--border-subtle);background:var(--bg-card);color:var(--text-secondary);cursor:pointer;font-size:12px;">Cancel</button></div>`);
    const cancelBtn = document.getElementById('cancel-query-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', () => { if (state.queryAbort) state.queryAbort.abort(); });

    try {
        const payload = {
            project_path: state.currentProject,
            symbol: symbol,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/impact', {
            method: 'POST',
            body: JSON.stringify(payload),
            signal: state.queryAbort.signal
        });

        addOperationHistory('impact', symbol);
        applyImpactOverlay(symbol, res);
        renderOperationResults(res.synthesized_report || 'No impact report generated.');
        showToast(`Blast radius: ${res.blast_radius_count || 0} dependent components (${res.risk_level || 'OK'})`, 'success');
    } catch (e) {
        if (e.name === 'AbortError') {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Impact analysis cancelled.</div>`);
            showToast('Impact analysis cancelled', 'info');
        } else {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Impact Error: ${escapeHtml(e.message)}</div>`);
            showToast(`Impact failed: ${e.message}`, 'error');
        }
    } finally {
        state.queryAbort = null;
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
    if (state.queryAbort) state.queryAbort.abort();
    state.queryAbort = new AbortController();
    setBusy(true);
    openDrawer();
    switchDrawerTab('results');
    setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);"><svg class="btn-spinner" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline-block;vertical-align:middle;margin-right:8px;"><circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle></svg>Tracing execution path: <strong>${escapeHtml(fromSym)} &rarr; ${escapeHtml(toSym)}</strong>...<button id="cancel-query-btn" style="margin-left:12px;padding:4px 12px;border-radius:6px;border:1px solid var(--border-subtle);background:var(--bg-card);color:var(--text-secondary);cursor:pointer;font-size:12px;">Cancel</button></div>`);
    const cancelBtn = document.getElementById('cancel-query-btn');
    if (cancelBtn) cancelBtn.addEventListener('click', () => { if (state.queryAbort) state.queryAbort.abort(); });

    try {
        const payload = {
            project_path: state.currentProject,
            from_symbol: fromSym,
            to_symbol: toSym,
            use_llm: state.useLlm
        };
        const res = await apiFetch('/api/trace', {
            method: 'POST',
            body: JSON.stringify(payload),
            signal: state.queryAbort.signal
        });

        addOperationHistory('trace', `${fromSym} -> ${toSym}`);
        applyTraceOverlay(res);
        renderOperationResults(res.synthesized_flow || 'No path found.');
        showToast(res.path_found ? `Trace path found: ${res.path_length || 0} steps` : 'No path found between symbols', res.path_found ? 'success' : 'info');
    } catch (e) {
        if (e.name === 'AbortError') {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--text-secondary);">Trace cancelled.</div>`);
            showToast('Trace cancelled', 'info');
        } else {
            setSafeHtml(els.resultsOutput, `<div style="padding:16px;color:var(--accent-rose);">Trace Error: ${escapeHtml(e.message)}</div>`);
            showToast(`Trace failed: ${e.message}`, 'error');
        }
    } finally {
        state.queryAbort = null;
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
    showToast('Started 3-Tier Indexing pipeline', 'info');

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
        showToast('Indexing completed! Reloading knowledge graph...', 'success');
        loadProject();
    } else {
        showToast(`Indexing issue: ${msg}`, 'error');
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
        showToast('Indexing cancelled', 'info');
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
    const emptyText = els.opsHistory.querySelector('.empty-ops-text');
    if (emptyText) emptyText.remove();

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
