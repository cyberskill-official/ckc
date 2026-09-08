// ==========================================================================
// CKC Graph-First Explorer Engine (3D WebGL Spatial & 2D Cytoscape)
// Engineered with NextLevelBuilder UI/UX Pro Max Design Intelligence
// ==========================================================================

const state = {
    currentProject: localStorage.getItem('ckc_project_path') || '',
    uiToken: localStorage.getItem('ckc_ui_token') || '',
    useLlm: localStorage.getItem('ckc_use_llm') !== '0',
    viewMode: '3d', // '3d' (default) or '2d'
    graph3d: null,
    cy: null,
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

if (window.mermaid) {
    mermaid.initialize({
        startOnLoad: false,
        securityLevel: 'strict',
        theme: 'dark'
    });
}

const els = {
    // Header
    projectInput: document.getElementById('project-path'),
    uiTokenInput: document.getElementById('ui-token'),
    samplePicker: document.getElementById('sample-picker'),
    loadBtn: document.getElementById('load-btn'),
    readyBadge: document.getElementById('ready-badge'),
    readyBadgeText: document.querySelector('#ready-badge .badge-text'),
    docsChip: document.getElementById('docs-chip'),
    llmChip: document.getElementById('llm-chip'),
    viewMode3dBtn: document.getElementById('view-mode-3d'),
    viewMode2dBtn: document.getElementById('view-mode-2d'),
    autoRotateBtn: document.getElementById('auto-rotate-btn'),
    fitBtn: document.getElementById('fit-btn'),
    resetCamBtn: document.getElementById('reset-cam-btn'),
    toggleSidebarBtn: document.getElementById('toggle-sidebar-btn'),

    // Popovers & Header Trigger Buttons
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

    // Sidebar & Layers
    sidebar: document.getElementById('sidebar'),
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
    container2d: document.getElementById('cy'),
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
// Initialization
// ==========================================================================

function init() {
    els.projectInput.value = state.currentProject;
    if (els.uiTokenInput) {
        els.uiTokenInput.value = state.uiToken;
    }
    if (els.useLlm) {
        els.useLlm.checked = state.useLlm;
    }

    updateProjectLabel();
    init3DGraph();
    initCytoscape();
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
        els.currentProjectLabel.title = 'Click to switch repository';
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
    if (typeof detail === 'object') {
        return detail.msg || detail.message || JSON.stringify(detail);
    }
    return String(detail);
}

async function apiFetch(url, options) {
    const opts = Object.assign({}, options || {});
    opts.headers = authHeaders(opts.headers);
    const res = await fetch(url, opts);
    let body = null;
    try {
        body = await res.json();
    } catch (_e) {
        body = null;
    }
    if (!res.ok) {
        const detail = body && body.detail != null ? formatApiDetail(body.detail) : res.statusText;
        const err = new Error(detail);
        err.status = res.status;
        throw err;
    }
    return body;
}

function setBusy(busy) {
    state.inFlight = busy;
    els.loadBtn.disabled = busy;
    els.runIndexBtn.disabled = busy;
    els.commandBar.disabled = busy;
    els.actionImpact.disabled = busy;
    els.actionTrace.disabled = busy;
    els.actionQuery.disabled = busy;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function setSafeHtml(el, html) {
    const clean = window.DOMPurify
        ? DOMPurify.sanitize(html, { USE_PROFILES: { html: true } })
        : html;
    el.innerHTML = clean;
}

function renderMarkdown(text) {
    const raw = marked.parse(text || '');
    return window.DOMPurify
        ? DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
        : raw;
}

async function loadSamples() {
    try {
        const data = await apiFetch('/api/samples');
        const samples = data.samples || [];
        samples.forEach((s) => {
            const opt = document.createElement('option');
            opt.value = s.path;
            opt.textContent = s.name;
            els.samplePicker.appendChild(opt);
        });
    } catch (e) {
        console.warn('Failed to load samples:', e);
    }
}

function getCommunityColor(commId) {
    if (commId == null) return '#94a3b8';
    let hash = 0;
    const str = String(commId);
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return state.palette[Math.abs(hash) % state.palette.length];
}

function getNodeColor(node) {
    if (node.category === 'doc') return '#c084fc';
    if (node.category === 'schema') return '#fbbf24';
    if (node.category === 'test') return '#34d399';
    return getCommunityColor(node.community);
}

// ==========================================================================
// 3D Graph Engine (Three.js & 3D Force-Directed Graph)
// ==========================================================================

function init3DGraph() {
    if (!els.container3d || !window.ForceGraph3D) {
        console.warn('ForceGraph3D CDN not available, relying on 2D');
        return;
    }

    try {
        state.graph3d = ForceGraph3D({ controlType: 'orbit' })(els.container3d)
            .backgroundColor('#070a12')
            .showNavInfo(false)
            .nodeId('id')
            .nodeLabel(n => `<div style="background:rgba(15,23,42,0.92);padding:8px 12px;border-radius:8px;border:1px solid #38bdf8;color:#f8fafc;font-family:var(--font-mono);font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,0.5);"><b style="color:#38bdf8">${escapeHtml(n.label || n.id)}</b> <span style="opacity:0.7">[${escapeHtml(n.category || 'code')}]</span><br><span style="font-size:11px;color:#94a3b8">Degree: ${n.degree || 0} • Community ${n.community ?? 'none'}</span><br><span style="font-size:10px;color:#64748b">${escapeHtml(n.source_file || '')}</span></div>`)
            .nodeVal(n => Math.sqrt(n.degree || 1) * 2.5 + 3.0)
            .nodeResolution(16)
            .nodeColor(n => getNodeColor(n))
            .linkSource('source')
            .linkTarget('target')
            .linkOpacity(0.35)
            .linkColor(link => {
                if (link.__highlight) return '#38bdf8';
                return 'rgba(255, 255, 255, 0.12)';
            })
            .linkWidth(link => (link.__highlight ? 2.5 : 0.8))
            .linkDirectionalParticles(link => link.__particles || 0)
            .linkDirectionalParticleSpeed(link => link.__particleSpeed || 0.007)
            .linkDirectionalParticleWidth(link => link.__particleWidth || 3.0)
            .linkDirectionalArrowLength(3.5)
            .linkDirectionalArrowRelPos(1)
            .onNodeClick((node, event) => {
                if (event?.shiftKey) {
                    handleShiftClick(node);
                } else {
                    selectNode(node);
                }
            })
            .onNodeHover((node, prevNode) => {
                if (els.container3d) {
                    els.container3d.style.cursor = node ? 'pointer' : 'default';
                }
            })
            .onBackgroundClick(() => {
                clearSelection();
                closeAllPopovers();
            });

        // Fine-tune 3D force physics for natural community separation
        state.graph3d.d3Force('charge').strength(-90);
        state.graph3d.d3Force('link').distance(40);
        
    } catch (e) {
        console.error('Error initializing 3D Force Graph:', e);
    }
}

function flyToNode(node, distance = 85) {
    if (!state.graph3d || !node) return;
    const nx = node.x || 0;
    const ny = node.y || 0;
    const nz = node.z || 0;
    const dist = Math.hypot(nx, ny, nz) || 1;
    const ratio = 1 + distance / dist;

    state.graph3d.cameraPosition(
        { x: nx * ratio, y: ny * ratio + 15, z: nz * ratio + 30 },
        { x: nx, y: ny, z: nz },
        900
    );
}

// ==========================================================================
// 2D Graph Engine (Cytoscape.js Fallback)
// ==========================================================================

function initCytoscape() {
    if (!els.container2d || !window.cytoscape) return;

    state.cy = cytoscape({
        container: els.container2d,
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'font-size': '10px',
                    'font-family': 'JetBrains Mono, monospace',
                    'color': '#c9d1d9',
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-margin-y': 4,
                    'min-zoomed-font-size': 8
                }
            },
            {
                selector: 'node[category="code"]',
                style: { 'shape': 'ellipse', 'background-color': '#38bdf8' }
            },
            {
                selector: 'node[category="doc"]',
                style: { 'shape': 'diamond', 'background-color': '#c084fc' }
            },
            {
                selector: 'node[category="schema"]',
                style: { 'shape': 'hexagon', 'background-color': '#fbbf24' }
            },
            {
                selector: 'node[category="test"]',
                style: { 'shape': 'triangle', 'background-color': '#34d399' }
            },
            {
                selector: 'edge',
                style: {
                    'width': 1,
                    'line-color': '#334155',
                    'curve-style': 'bezier',
                    'target-arrow-shape': 'triangle',
                    'target-arrow-color': '#334155',
                    'arrow-scale': 0.8
                }
            },
            {
                selector: ':selected',
                style: {
                    'border-width': 3,
                    'border-color': '#38bdf8'
                }
            },
            {
                selector: '.dimmed',
                style: { 'opacity': 0.25 }
            },
            {
                selector: '.trace-source',
                style: {
                    'border-width': 3,
                    'border-color': '#f59e0b'
                }
            },
            {
                selector: '.impact-target',
                style: { 'background-color': '#f43f5e', 'border-color': '#f43f5e', 'border-width': 3 }
            },
            {
                selector: '.impact-node',
                style: { 'background-color': '#f59e0b' }
            },
            {
                selector: '.trace-edge',
                style: {
                    'line-color': '#38bdf8',
                    'target-arrow-color': '#38bdf8',
                    'width': 3,
                    'line-style': 'dashed'
                }
            }
        ],
        layout: { name: 'grid' }
    });

    state.cy.on('tap', 'node', function(evt){
        const node = evt.target;
        if (evt.originalEvent?.shiftKey) {
            handleShiftClick(node.data());
        } else {
            selectNode(node.data());
        }
    });

    state.cy.on('tap', function(evt){
        if (evt.target === state.cy) {
            clearSelection();
        }
    });
}

// ==========================================================================
// Event Listeners & Controls
// ==========================================================================

function setupEventListeners() {
    // Popover Toggles
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

    // Close popovers on click outside
    document.addEventListener('pointerdown', (e) => {
        if (!e.target.closest('.floating-popover') &&
            !e.target.closest('.project-pill') &&
            !e.target.closest('#layers-toggle-btn') &&
            !e.target.closest('#header-index-btn') &&
            !e.target.closest('#ready-badge')) {
            closeAllPopovers();
        }
    });

    // Project loading
    els.loadBtn.addEventListener('click', () => {
        persistUiTokenFromInput();
        state.currentProject = els.projectInput.value;
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

    // Viewport Mode Switcher (3D vs 2D)
    els.viewMode3dBtn.addEventListener('click', () => switchViewMode('3d'));
    els.viewMode2dBtn.addEventListener('click', () => switchViewMode('2d'));

    // Camera Controls
    els.autoRotateBtn.addEventListener('click', toggleAutoRotate);
    els.fitBtn.addEventListener('click', fitGraphView);
    els.resetCamBtn.addEventListener('click', resetCameraView);

    // Sidebar Toggle (compatibility)
    if (els.toggleSidebarBtn && els.sidebar) {
        els.toggleSidebarBtn.addEventListener('click', () => {
            els.sidebar.classList.toggle('collapsed');
            setTimeout(() => {
                if (state.graph3d && els.container3d) {
                    state.graph3d.width(els.graphViewport.clientWidth);
                    state.graph3d.height(els.graphViewport.clientHeight);
                }
                if (state.cy) state.cy.resize();
            }, 320);
        });
    }

    // Filters
    ['Code', 'Doc', 'Schema', 'Test'].forEach(type => {
        els[`filter${type}`].addEventListener('change', (e) => {
            state.filters[type.toLowerCase()] = e.target.checked;
            applyFilters();
        });
    });

    // Context Panel Close
    els.closePanelBtn.addEventListener('click', () => {
        els.contextPanel.classList.add('closed');
        clearSelection();
    });

    // Copy Symbol Name Button
    els.copySymbolNameBtn.addEventListener('click', () => {
        if (state.selectedNode) {
            navigator.clipboard.writeText(state.selectedNode.label || state.selectedNode.id);
            els.copySymbolNameBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            setTimeout(() => {
                els.copySymbolNameBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
            }, 1500);
        }
    });

    // Bottom Drawer
    els.drawerToggle.addEventListener('click', (e) => {
        if (e.target.closest('.drawer-tabs') || e.target.closest('#copy-results-btn')) return;
        toggleDrawer();
    });

    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetBtn = e.target.closest('.tab-btn');
            if (!targetBtn) return;
            els.tabBtns.forEach(b => b.classList.remove('active'));
            targetBtn.classList.add('active');

            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            const pane = document.getElementById(`pane-${targetBtn.dataset.tab}`);
            if (pane) pane.classList.add('active');
            state.drawerTab = targetBtn.dataset.tab;
            if (!state.drawerOpen) openDrawer();
        });
    });

    els.copyResultsBtn.addEventListener('click', () => {
        if (state.lastResults) {
            navigator.clipboard.writeText(state.lastResults);
            els.copyResultsBtn.textContent = 'Copied!';
            setTimeout(() => { els.copyResultsBtn.textContent = 'Copy Markdown'; }, 1800);
        }
    });

    // Command Bar
    els.commandBar.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleCommand(e.target.value);
    });

    els.modeBadges.forEach(badge => {
        badge.addEventListener('click', () => {
            els.modeBadges.forEach(b => b.classList.remove('active'));
            badge.classList.add('active');
        });
    });

    els.clearOverlaysBtn.addEventListener('click', clearOverlays);

    // Global Hotkeys
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAllPopovers();
            clearSelection();
            clearOverlays();
            els.contextPanel.classList.add('closed');
        } else if (e.key === '/' && document.activeElement !== els.commandBar && document.activeElement.tagName !== 'INPUT') {
            e.preventDefault();
            els.commandBar.focus();
        } else if (e.key === 'f' && document.activeElement.tagName !== 'INPUT') {
            fitGraphView();
        } else if ((e.key === 'l' || e.key === 'L') && document.activeElement.tagName !== 'INPUT') {
            e.preventDefault();
            if (els.layersToggleBtn) els.layersToggleBtn.click();
        }
    });

    // Indexing Actions
    els.runIndexBtn.addEventListener('click', () => {
        closeAllPopovers();
        runIndexing();
    });
    els.cancelIndexBtn.addEventListener('click', cancelIndexing);

    // Window Resize
    window.addEventListener('resize', () => {
        if (state.graph3d && els.container3d) {
            state.graph3d.width(els.graphViewport.clientWidth);
            state.graph3d.height(els.graphViewport.clientHeight);
        }
        if (state.cy) state.cy.resize();
    });
}

function switchViewMode(mode) {
    state.viewMode = mode;
    if (mode === '3d') {
        els.viewMode3dBtn.classList.add('active');
        els.viewMode2dBtn.classList.remove('active');
        els.container3d.classList.remove('hidden');
        els.container2d.classList.add('hidden');
        if (state.graph3d) {
            state.graph3d.width(els.graphViewport.clientWidth);
            state.graph3d.height(els.graphViewport.clientHeight);
        }
    } else {
        els.viewMode2dBtn.classList.add('active');
        els.viewMode3dBtn.classList.remove('active');
        els.container2d.classList.remove('hidden');
        els.container3d.classList.add('hidden');
        if (state.cy) {
            state.cy.resize();
            state.cy.fit(50);
        }
    }
}

function toggleAutoRotate() {
    state.isAutoRotating = !state.isAutoRotating;
    els.autoRotateBtn.classList.toggle('active', state.isAutoRotating);
    if (state.graph3d && state.graph3d.controls) {
        state.graph3d.controls().autoRotate = state.isAutoRotating;
        state.graph3d.controls().autoRotateSpeed = 0.8;
    }
}

function fitGraphView() {
    if (state.viewMode === '3d' && state.graph3d) {
        state.graph3d.zoomToFit(800, 35);
    } else if (state.cy) {
        state.cy.fit(50);
    }
}

function resetCameraView() {
    if (state.viewMode === '3d' && state.graph3d) {
        state.graph3d.cameraPosition({ x: 0, y: 0, z: 420 }, { x: 0, y: 0, z: 0 }, 800);
    } else if (state.cy) {
        state.cy.reset();
        state.cy.fit(50);
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
        els.readyBadge.className = 'badge badge-error';
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
        els.readyBadge.className = 'badge badge-ready';
        if (els.readyBadgeText) els.readyBadgeText.textContent = 'Ready (3/3)';
    } else {
        const count = res.status?.ready_count ?? 0;
        els.readyBadge.className = 'badge badge-neutral';
        if (els.readyBadgeText) els.readyBadgeText.textContent = `${count}/3 Ready`;
    }

    const docs = res.local_docs_count;
    if (typeof docs === 'number') {
        els.docsChip.textContent = `Docs: ${docs}`;
        els.docsChip.className = 'badge badge-ready';
    } else {
        els.docsChip.textContent = 'Docs: —';
        els.docsChip.className = 'badge badge-muted';
    }

    if (res.llm && res.llm.configured) {
        els.llmChip.textContent = `LLM: ${res.llm.model || 'Active'}`;
        els.llmChip.className = 'badge badge-ready';
    } else {
        els.llmChip.textContent = 'LLM: Off';
        els.llmChip.className = 'badge badge-muted';
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
        counts[cat] = (counts[cat] || 0) + 1;
    });
    els.countCode.textContent = counts.code || 0;
    els.countDoc.textContent = counts.doc || 0;
    els.countSchema.textContent = counts.schema || 0;
    els.countTest.textContent = counts.test || 0;

    // Populate communities list
    renderCommunities();

    // 1. Render 3D Graph
    if (state.graph3d) {
        const gData = {
            nodes: rawNodes.map(n => Object.assign({}, n)),
            links: rawLinks.map(l => Object.assign({}, l))
        };
        state.graph3d.graphData(gData);
        setTimeout(() => fitGraphView(), 600);
    }

    // 2. Render 2D Cytoscape fallback
    if (state.cy) {
        state.cy.elements().remove();
        state.cy.add(res.elements);

        state.cy.nodes().forEach(node => {
            const degree = node.data('degree') || 1;
            const size = Math.max(20, Math.min(55, 20 + degree * 2.5));
            node.style({
                'width': size,
                'height': size,
                'background-color': getNodeColor(node.data())
            });
        });

        try {
            state.cy.layout({
                name: 'cose',
                animate: false,
                randomize: true,
                idealEdgeLength: 70,
                nodeRepulsion: 6000
            }).run();
        } catch (_e) {
            state.cy.layout({ name: 'grid' }).run();
        }
    }
}

function renderCommunities() {
    els.communityList.innerHTML = '';
    const total = state.communities.length;
    els.commTotalBadge.textContent = `${total} cluster${total === 1 ? '' : 's'}`;

    state.communities.sort((a,b) => b.size - a.size).slice(0, 18).forEach(c => {
        const li = document.createElement('li');
        const color = getCommunityColor(c.id);
        li.innerHTML = `<span class="comm-color" style="background:${color}"></span> <span>Community ${c.id}</span> <span style="margin-left:auto;opacity:0.6">${c.size}</span>`;
        li.addEventListener('click', () => {
            focusCommunity(c.id);
        });
        els.communityList.appendChild(li);
    });
}

function focusCommunity(commId) {
    if (state.viewMode === '3d' && state.graph3d) {
        const nodes = state.graph3d.graphData().nodes.filter(n => n.community === commId);
        if (nodes.length) {
            // Find centroid of community
            let cx = 0, cy = 0, cz = 0;
            nodes.forEach(n => { cx += n.x || 0; cy += n.y || 0; cz += n.z || 0; });
            cx /= nodes.length; cy /= nodes.length; cz /= nodes.length;

            state.graph3d.cameraPosition(
                { x: cx * 1.5, y: cy * 1.5 + 40, z: cz * 1.5 + 80 },
                { x: cx, y: cy, z: cz },
                1000
            );

            // Highlight community nodes
            state.highlightNodes = new Set(nodes.map(n => n.id));
            state.graph3d.nodeColor(state.graph3d.nodeColor());
        }
    } else if (state.cy) {
        const nodes = state.cy.nodes().filter(n => n.data('community') === commId);
        if (nodes.length) {
            state.cy.nodes().addClass('dimmed');
            nodes.removeClass('dimmed');
            state.cy.fit(nodes, 50);
        }
    }
}

function applyFilters() {
    // 3D Filters
    if (state.graph3d && state.graphData) {
        const rawNodes = state.graphData.elements.nodes.map(n => n.data);
        const filteredNodes = rawNodes.filter(n => state.filters[n.category || 'code']);
        const validIds = new Set(filteredNodes.map(n => n.id));
        const rawLinks = state.graphData.elements.edges.map(e => e.data);
        const filteredLinks = rawLinks.filter(l => {
            const src = typeof l.source === 'object' ? l.source.id : l.source;
            const tgt = typeof l.target === 'object' ? l.target.id : l.target;
            return validIds.has(src) && validIds.has(tgt);
        });

        state.graph3d.graphData({
            nodes: filteredNodes.map(n => Object.assign({}, n)),
            links: filteredLinks.map(l => Object.assign({}, l))
        });
    }

    // 2D Filters
    if (state.cy) {
        state.cy.nodes().forEach(node => {
            const cat = node.data('category') || 'code';
            if (state.filters[cat]) node.style('display', 'element');
            else node.style('display', 'none');
        });
    }
}

// ==========================================================================
// Node Selection & Context Inspector
// ==========================================================================

function selectNode(data) {
    if (!data) return;
    state.selectedNode = data;

    // 1. Update 3D graph highlights & camera
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

    // 2. Update 2D Cytoscape highlights
    if (state.cy) {
        const cyNode = state.cy.getElementById(data.id);
        if (cyNode.length) {
            state.cy.nodes().addClass('dimmed');
            cyNode.removeClass('dimmed');
            cyNode.neighborhood().removeClass('dimmed');
        }
    }

    // 3. Populate Right Context Panel
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

    if (state.cy) {
        state.cy.nodes().removeClass('dimmed');
    }

    els.contextPanel.classList.add('closed');
}

function handleShiftClick(data) {
    if (!state.traceSource) {
        state.traceSource = data.id;
        els.commandBar.placeholder = `Select target destination node for trace from ${data.label || data.id}...`;
        if (state.cy) state.cy.getElementById(data.id).addClass('trace-source');
    } else if (state.traceSource !== data.id) {
        runTrace(state.traceSource, data.id);
        if (state.cy) state.cy.getElementById(state.traceSource).removeClass('trace-source');
        state.traceSource = null;
        els.commandBar.placeholder = "Search symbols, ask architectural questions, or type 'A -> B' to trace... (Press '/')";
    }
}

function showContextPanel(data) {
    closeAllPopovers();
    els.contextPanel.classList.remove('closed');
    document.querySelector('.empty-state')?.classList.add('hidden');
    document.querySelector('.node-info')?.classList.remove('hidden');

    const label = data.label || data.id;
    els.nodeLabel.textContent = label;
    els.nodeCategory.textContent = data.category || 'code';
    els.nodeCategory.className = `badge cat-${data.category || 'code'}`;
    els.nodeTypeBadge.textContent = data.file_type || (data.is_class ? 'class' : (data.is_callable ? 'callable' : 'symbol'));

    els.nodeSource.textContent = (data.source_file || '') + (data.source_location ? `:${data.source_location}` : '');
    els.nodeCommunity.textContent = data.community != null ? `Community ${data.community}` : 'None';
    els.nodeDegree.textContent = data.degree || 0;

    // Build connections list grouped by relation
    els.nodeConnections.innerHTML = '';
    const grouped = {};
    if (state.graphData && state.graphData.elements.edges) {
        state.graphData.elements.edges.forEach(edge => {
            const e = edge.data;
            if (e.source === data.id) {
                const rel = e.relation || 'out';
                if (!grouped[rel]) grouped[rel] = [];
                grouped[rel].push(e.target);
            } else if (e.target === data.id) {
                const rel = `in (${e.relation || 'ref'})`;
                if (!grouped[rel]) grouped[rel] = [];
                grouped[rel].push(e.source);
            }
        });
    }

    if (Object.keys(grouped).length === 0) {
        els.nodeConnections.innerHTML = '<div style="color:var(--text-muted);font-size:0.75rem;">No direct connections recorded.</div>';
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

            nodeIds.slice(0, 12).forEach(tid => {
                const a = document.createElement('a');
                a.className = 'symbol-link';
                // Resolve friendly label
                let friendly = tid;
                if (state.graphData) {
                    const found = state.graphData.elements.nodes.find(n => n.data.id === tid);
                    if (found) friendly = found.data.label || tid;
                }
                a.textContent = friendly;
                a.title = tid;
                a.onclick = () => selectNodeByLabel(friendly);
                chipsDiv.appendChild(a);
            });

            if (nodeIds.length > 12) {
                const more = document.createElement('span');
                more.style.cssText = 'color:var(--text-muted);font-size:0.7rem;align-self:center;';
                more.textContent = `+${nodeIds.length - 12} more`;
                chipsDiv.appendChild(more);
            }

            groupDiv.appendChild(chipsDiv);
            els.nodeConnections.appendChild(groupDiv);
        }
    }

    // Action button triggers
    els.actionImpact.onclick = () => runImpact(label);
    els.actionTrace.onclick = () => {
        state.traceSource = data.id;
        els.commandBar.placeholder = `Select destination node to trace path from ${label}...`;
        if (state.cy) state.cy.getElementById(data.id).addClass('trace-source');
    };
    els.actionQuery.onclick = () => runQuery(`Explain the architecture and purpose of ${label}`);
}

window.selectNodeByLabel = function(label) {
    if (!state.graphData) return;
    const lower = label.toLowerCase();
    const found = state.graphData.elements.nodes.find(n => 
        (n.data.label || '').toLowerCase() === lower || n.data.id.toLowerCase() === lower
    );
    if (found) {
        selectNode(found.data);
    }
};

// ==========================================================================
// Operations (Query, Impact, Trace, Indexing)
// ==========================================================================

async function handleCommand(val) {
    if (!val || !val.trim()) return;
    const q = val.trim();

    if (q.includes('->') || q.includes('→') || q.includes('=>')) {
        const parts = q.split(/->|→|=>/);
        if (parts.length === 2) {
            runTrace(parts[0].trim(), parts[1].trim());
            els.commandBar.value = '';
            return;
        }
    }

    // Direct symbol match on graph
    if (state.graphData) {
        const match = state.graphData.elements.nodes.find(n => 
            (n.data.label || '').toLowerCase() === q.toLowerCase() || n.data.id.toLowerCase() === q.toLowerCase()
        );
        if (match) {
            selectNode(match.data);
            els.commandBar.value = '';
            return;
        }
    }

    // Auto-routing: Single identifier -> Impact analysis; Natural language -> Query
    if (/^[a-zA-Z0-9_:.#-]+$/.test(q) && !q.includes(' ')) {
        runImpact(q);
    } else {
        runQuery(q);
    }
    els.commandBar.value = '';
}

function openDrawer(tab) {
    els.drawer.classList.add('open');
    state.drawerOpen = true;
    if (tab) {
        const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
        if (btn) btn.click();
    }
}

function toggleDrawer() {
    if (state.drawerOpen) {
        els.drawer.classList.remove('open');
    } else {
        els.drawer.classList.add('open');
    }
    state.drawerOpen = !state.drawerOpen;
}

function clearOverlays() {
    // 3D graph reset
    if (state.graph3d) {
        const gData = state.graph3d.graphData();
        gData.nodes.forEach(n => {
            n.__isTarget = false;
            n.__isCaller = false;
            n.__isTraceHop = false;
        });
        gData.links.forEach(l => {
            l.__highlight = false;
            l.__particles = 0;
        });
        state.highlightNodes.clear();
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());
    }

    // 2D cytoscape reset
    if (state.cy) {
        state.cy.elements().removeClass('impact-target impact-node trace-edge trace-source dimmed');
    }

    els.clearOverlaysBtn.classList.add('hidden');
}

function addOpToHistory(type, label) {
    const chip = document.createElement('div');
    chip.className = 'op-chip';
    chip.textContent = `${type.toUpperCase()}: ${label}`;
    chip.onclick = () => {
        if (type === 'impact') runImpact(label);
        else if (type === 'query') runQuery(label);
    };
    els.opsHistory.prepend(chip);
    if (els.opsHistory.children.length > 5) els.opsHistory.lastChild.remove();
}

async function runQuery(q) {
    openDrawer('results');
    setSafeHtml(els.resultsOutput, '<i>Searching architecture & cross-domain graph…</i>');
    addOpToHistory('query', q.substring(0, 24));
    els.copyResultsBtn.classList.add('hidden');

    try {
        const res = await apiFetch('/api/query', {
            method: 'POST',
            body: JSON.stringify({
                project_path: state.currentProject,
                query: q,
                use_llm: state.useLlm
            })
        });

        const markdown = res.synthesized_context || JSON.stringify(res, null, 2);
        state.lastResults = markdown;
        setSafeHtml(els.resultsOutput, linkifySymbols(renderMarkdown(markdown)));
        els.copyResultsBtn.classList.remove('hidden');
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<span style="color:var(--accent-rose)">Error: ${escapeHtml(e.message)}</span>`);
    }
}

async function runImpact(symbol) {
    clearOverlays();
    openDrawer('results');
    setSafeHtml(els.resultsOutput, `<i>Calculating blast radius for <code>${escapeHtml(symbol)}</code>…</i>`);
    els.clearOverlaysBtn.classList.remove('hidden');
    addOpToHistory('impact', symbol);
    els.copyResultsBtn.classList.add('hidden');

    try {
        const res = await apiFetch('/api/impact', {
            method: 'POST',
            body: JSON.stringify({
                project_path: state.currentProject,
                symbol: symbol,
                use_llm: state.useLlm
            })
        });

        const markdown = res.synthesized_report || JSON.stringify(res, null, 2);
        state.lastResults = markdown;
        setSafeHtml(els.resultsOutput, linkifySymbols(renderMarkdown(markdown)));
        els.copyResultsBtn.classList.remove('hidden');

        // 3D Graph Impact Highlight
        if (state.graph3d) {
            const symLower = symbol.toLowerCase();
            const gNodes = state.graph3d.graphData().nodes;
            const target = gNodes.find(n => (n.label || '').toLowerCase() === symLower || n.id.toLowerCase() === symLower);

            const callerSyms = new Set((res.call_hierarchy || []).map(c => (c.symbol || '').toLowerCase()));
            const affectedNodeIds = new Set();

            gNodes.forEach(n => {
                const l = (n.label || '').toLowerCase();
                if (target && n.id === target.id) {
                    n.__isTarget = true;
                    affectedNodeIds.add(n.id);
                } else if (callerSyms.has(l)) {
                    n.__isCaller = true;
                    affectedNodeIds.add(n.id);
                }
            });

            // Particles flowing to blast radius
            state.graph3d.graphData().links.forEach(l => {
                const s = typeof l.source === 'object' ? l.source.id : l.source;
                const t = typeof l.target === 'object' ? l.target.id : l.target;
                if (affectedNodeIds.has(s) || affectedNodeIds.has(t)) {
                    l.__highlight = true;
                    l.__particles = 3;
                    l.__particleSpeed = 0.01;
                }
            });

            state.highlightNodes = affectedNodeIds;
            state.graph3d.nodeColor(state.graph3d.nodeColor());
            state.graph3d.linkColor(state.graph3d.linkColor());
            state.graph3d.linkWidth(state.graph3d.linkWidth());
            state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());

            if (target) flyToNode(target);
        }

        // 2D Cytoscape Impact Highlight
        if (state.cy) {
            const match = state.cy.nodes().filter(n => (n.data('label') || '').toLowerCase() === symbol.toLowerCase());
            if (match.length) match[0].addClass('impact-target');
            if (res.call_hierarchy) {
                res.call_hierarchy.forEach(item => {
                    const cMatch = state.cy.nodes().filter(n => (n.data('label') || '').toLowerCase() === (item.symbol || '').toLowerCase());
                    if (cMatch.length) cMatch[0].addClass('impact-node');
                });
            }
        }
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<span style="color:var(--accent-rose)">Error: ${escapeHtml(e.message)}</span>`);
    }
}

async function runTrace(fromSym, toSym) {
    clearOverlays();
    openDrawer('results');
    setSafeHtml(els.resultsOutput, `<i>Tracing execution path <code>${escapeHtml(fromSym)}</code> ➔ <code>${escapeHtml(toSym)}</code>…</i>`);
    els.clearOverlaysBtn.classList.remove('hidden');
    addOpToHistory('trace', `${fromSym}→${toSym}`);
    els.copyResultsBtn.classList.add('hidden');

    try {
        const res = await apiFetch('/api/trace', {
            method: 'POST',
            body: JSON.stringify({
                project_path: state.currentProject,
                from_symbol: fromSym,
                to_symbol: toSym,
                use_llm: state.useLlm
            })
        });

        const markdown = res.synthesized_flow || JSON.stringify(res, null, 2);
        state.lastResults = markdown;
        setSafeHtml(els.resultsOutput, linkifySymbols(renderMarkdown(markdown)));
        els.copyResultsBtn.classList.remove('hidden');

        // Highlight trace path in 3D
        let stepNames = [];
        if (res.steps && res.steps.length > 0) {
            stepNames = res.steps.map(s => (s.symbol_name || '').toLowerCase());
        } else if (markdown.includes('-->')) {
            const lines = markdown.split('\n');
            for (const line of lines) {
                if (line.includes('-->')) {
                    const hops = line.split(/\s*--.*?-->\s*/);
                    hops.forEach(h => {
                        const clean = h.trim().toLowerCase().replace(/^[`'"]+|[`'"]+$/g, '').replace(/\(\)$/, '');
                        if (clean) stepNames.push(clean);
                    });
                    break;
                }
            }
        }
        if (!stepNames.includes(fromSym.toLowerCase())) stepNames.unshift(fromSym.toLowerCase());
        if (!stepNames.includes(toSym.toLowerCase())) stepNames.push(toSym.toLowerCase());

        const cleanSteps = stepNames.map(s => s.toLowerCase().replace(/\(\)$/, '').replace(/^[`'"]+|[`'"]+$/g, '').trim()).filter(Boolean);

        if (cleanSteps.length > 0) {
            if (state.graph3d) {
                const gNodes = state.graph3d.graphData().nodes;
                const pathNodeIds = new Set();

                gNodes.forEach(n => {
                    const l = (n.label || '').toLowerCase().replace(/\(\)$/, '').trim();
                    const id = (n.id || '').toLowerCase().trim();
                    const isMatch = cleanSteps.some(s => s === l || s === id || l.endsWith(`.${s}`) || id.endsWith(`:${s}`) || id.endsWith(`::${s}`));
                    if (isMatch) {
                        n.__isTraceHop = true;
                        pathNodeIds.add(n.id);
                    }
                });

                // Stream particles continuously along trace hops
                state.graph3d.graphData().links.forEach(l => {
                    const s = typeof l.source === 'object' ? l.source.id : l.source;
                    const t = typeof l.target === 'object' ? l.target.id : l.target;
                    if (pathNodeIds.has(s) && pathNodeIds.has(t)) {
                        l.__highlight = true;
                        l.__particles = 4;
                        l.__particleSpeed = 0.012;
                        l.__particleWidth = 4.0;
                    }
                });

                state.highlightNodes = pathNodeIds;
                state.graph3d.nodeColor(state.graph3d.nodeColor());
                state.graph3d.linkColor(state.graph3d.linkColor());
                state.graph3d.linkWidth(state.graph3d.linkWidth());
                state.graph3d.linkDirectionalParticles(state.graph3d.linkDirectionalParticles());
            }

            if (state.cy) {
                cleanSteps.forEach(name => {
                    const match = state.cy.nodes().filter(n => {
                        const l = (n.data('label') || '').toLowerCase().replace(/\(\)$/, '').trim();
                        const id = (n.data('id') || '').toLowerCase().trim();
                        return l === name || id === name || l.endsWith(`.${name}`);
                    });
                    if (match.length) match[0].addClass('impact-node');
                });
            }
        }
    } catch (e) {
        setSafeHtml(els.resultsOutput, `<span style="color:var(--accent-rose)">Error: ${escapeHtml(e.message)}</span>`);
    }
}

// ==========================================================================
// Indexing Pipeline Execution & SSE Stream
// ==========================================================================

async function runIndexing() {
    if (!state.currentProject) return alert('Please load a repository first.');
    openDrawer('terminal');
    els.terminalOutput.textContent = '';
    els.runIndexBtn.classList.add('hidden');
    els.cancelIndexBtn.classList.remove('hidden');

    if (state.indexingAbort) {
        state.indexingCleanClose = true;
        state.indexingAbort.abort();
    }
    state.indexingCleanClose = false;
    state.indexingAbort = new AbortController();

    const force = !!els.forceIndex.checked;
    const multimodal = !!els.multimodalIndex.checked;

    appendTerminal('[CKC] Initializing 3-tier indexing pipeline...', 'info');

    try {
        const response = await fetch('/api/index/stream', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({
                project_path: state.currentProject,
                multimodal: multimodal,
                force: force
            }),
            signal: state.indexingAbort.signal
        });

        if (!response.ok) {
            let detail = response.statusText;
            try {
                const j = await response.json();
                detail = formatApiDetail(j.detail || j.message);
            } catch (_e) {}
            appendTerminal(`\nIndexing stream HTTP ${response.status}: ${detail}`, 'error');
            resetIndexButtons();
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                const trimmed = line.trim();
                if (trimmed.startsWith('data:')) {
                    const payload = trimmed.slice(5).trim();
                    if (payload) processIndexEvent(payload);
                }
            }
        }

        if (!state.indexingCleanClose) {
            appendTerminal('\n[CKC] Index stream concluded.', 'success');
            loadProject();
        }
    } catch (err) {
        if (err.name !== 'AbortError') {
            appendTerminal(`\n[Stream Error] ${err.message}`, 'error');
        }
    } finally {
        resetIndexButtons();
    }
}

async function cancelIndexing() {
    appendTerminal('\n[CKC] Requesting cancellation...', 'info');
    try {
        await apiFetch('/api/index/cancel', {
            method: 'POST',
            body: JSON.stringify({ project_path: state.currentProject })
        });
        appendTerminal('[CKC] Cancellation registered.', 'error');
    } catch (e) {
        appendTerminal(`[Cancel Error] ${e.message}`, 'error');
    }
}

function processIndexEvent(raw) {
    try {
        const data = JSON.parse(raw);
        if (data.event === 'start') {
            appendTerminal(`[CKC] ${data.message}`, 'info');
        } else if (data.event === 'step_start') {
            appendTerminal(`\n── [Step ${data.step}/${data.total_steps}] ${data.label} ──`, 'info');
        } else if (data.event === 'log') {
            appendTerminal(data.line, data.engine);
        } else if (data.event === 'step_finish') {
            const mark = data.success ? '✓' : '✗';
            appendTerminal(`[${data.engine}] ${mark} ${data.success ? 'Success' : 'Failed'}`, data.success ? 'success' : 'error');
        } else if (data.event === 'step_error') {
            appendTerminal(`[${data.engine}] Error: ${data.error}`, 'error');
        } else if (data.event === 'complete') {
            appendTerminal(`\n[CKC] 3-Tier indexing complete! (${data.status?.ready_count || 3}/3 Ready)`, 'success');
            loadProject();
        }
    } catch (_e) {
        appendTerminal(raw, '');
    }
}

function appendTerminal(text, type) {
    const div = document.createElement('div');
    div.className = `terminal-line ${type ? 'log-' + type : ''}`;
    div.textContent = text;
    els.terminalOutput.appendChild(div);
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
}

function resetIndexButtons() {
    els.runIndexBtn.classList.remove('hidden');
    els.cancelIndexBtn.classList.add('hidden');
}

/** Linkify recognized code symbols inside synthesized markdown reports */
function linkifySymbols(html) {
    if (!state.graphData) return html;
    const labels = new Set();
    state.graphData.elements.nodes.forEach(n => {
        const l = n.data.label;
        if (l && l.length > 2 && /^[a-zA-Z_]/.test(l)) labels.add(l);
    });

    let result = html;
    labels.forEach(label => {
        const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`<code>(${escaped})</code>`, 'g');
        result = result.replace(regex, `<code><a class="symbol-link" onclick="selectNodeByLabel('${label}')">$1</a></code>`);
    });
    return result;
}

window.onload = init;
