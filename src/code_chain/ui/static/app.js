// ==========================================================================
// CKC Graph-First Explorer Engine (100% 3D WebGL Spatial Universe)
// Designed with Linear/Raycast/Cursor Professional Developer Ergonomics
// ==========================================================================

const state = {
    currentProject: (() => {
        try {
            const urlParams = new URLSearchParams(window.location.search);
            return urlParams.get('project') || sessionStorage.getItem('ckc_project_path') || '';
        } catch (_) {
            return '';
        }
    })(),
    uiToken: localStorage.getItem('ckc_ui_token') || '',
    useLlm: localStorage.getItem('ckc_use_llm') !== '0',
    graph3d: null,
    selectedNode: null,
    traceSource: null,
    isTraceMode: false,
    graphData: null,
    communities: [],
    filters: {
        code: true,
        doc: true,
        schema: true,
        test: true,
        hideVendor: true,
        relCalls: true,
        relImports: true,
        relDefines: true,
        relInherits: true
    },
    layoutMode: '3d',
    incomingCallers: new Set(),
    outgoingCallees: new Set(),
    indexingTimer: null,
    indexingStartTime: null,
    isAutoRotating: false,
    prefersReducedMotion: typeof window !== 'undefined'
        && window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    indexingAbort: null,
    queryAbort: null,
    lastPopoverTrigger: null,
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
    byok: {
        provider: 'lm-studio',
        baseUrl: 'http://127.0.0.1:1234/v1',
        model: null,
        apiKey: '',
        connected: false,
        models: []
    },
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
    browseBtn: document.getElementById('browse-btn'),
    browsePathDisplay: document.getElementById('browse-path-display'),
    projectPathText: document.getElementById('project-path-text'),
    folderBrowserDialog: document.getElementById('folder-browser-dialog'),
    browserBreadcrumbs: document.getElementById('browser-breadcrumbs'),
    browserList: document.getElementById('browser-list'),
    browserSelectedPath: document.getElementById('browser-selected-path'),
    browserSelectBtn: document.getElementById('browser-select-btn'),
    browserCancelBtn: document.getElementById('browser-cancel-btn'),
    browserCloseBtn: document.getElementById('browser-close-btn'),
    browserQuickHome: document.getElementById('browser-quick-home'),
    browserQuickRoot: document.getElementById('browser-quick-root'),
    helpTourBtn: document.getElementById('help-tour-btn'),
    headerAiBtn: document.getElementById('header-ai-btn'),
    headerAiDot: document.getElementById('header-ai-dot'),
    headerAiLabel: document.getElementById('header-ai-label'),
    byokDialog: document.getElementById('byok-dialog'),
    byokCloseBtn: document.getElementById('byok-close-btn'),
    byokCancelBtn: document.getElementById('byok-cancel-btn'),
    byokSaveBtn: document.getElementById('byok-save-btn'),
    byokSkipBtn: document.getElementById('byok-skip-btn'),
    byokRetryBtn: document.getElementById('byok-retry-btn'),
    byokBaseUrl: document.getElementById('byok-base-url'),
    byokModelSelect: document.getElementById('byok-model-select'),
    byokModelCustom: document.getElementById('byok-model-custom'),
    byokApiKey: document.getElementById('byok-api-key'),
    byokToggleKey: document.getElementById('byok-toggle-key'),
    loadBtn: document.getElementById('load-btn'),
    readyBadge: document.getElementById('ready-badge'),
    readyBadgeText: document.querySelector('#ready-badge .badge-text'),
    docsChip: document.getElementById('docs-chip'),
    llmChip: document.getElementById('llm-chip'),
    recentProjectsList: document.getElementById('recent-projects-list'),
    clearRecentProjectsBtn: document.getElementById('clear-recent-projects-btn'),
    openByokFromIndexBtn: document.getElementById('open-byok-from-index-btn'),
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
    filterHideVendor: document.getElementById('filter-hide-vendor'),
    filterCode: document.getElementById('filter-code'),
    filterDoc: document.getElementById('filter-doc'),
    filterSchema: document.getElementById('filter-schema'),
    filterTest: document.getElementById('filter-test'),
    filterRelCalls: document.getElementById('filter-rel-calls'),
    filterRelImports: document.getElementById('filter-rel-imports'),
    filterRelDefines: document.getElementById('filter-rel-defines'),
    filterRelInherits: document.getElementById('filter-rel-inherits'),
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
    graphLayoutModes: document.getElementById('graph-layout-modes'),
    mode3dBtn: document.getElementById('mode-3d-btn'),
    mode2dBtn: document.getElementById('mode-2d-btn'),
    modeDagBtn: document.getElementById('mode-dag-btn'),

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
    nodeInDegree: document.getElementById('node-in-degree'),
    nodeOutDegree: document.getElementById('node-out-degree'),
    nodeConnections: document.getElementById('node-connections'),
    copySymbolNameBtn: document.getElementById('copy-symbol-name-btn'),
    copySourcePathBtn: document.getElementById('copy-source-path-btn'),
    actionFocusNode: document.getElementById('action-focus-node'),
    actionTraceFrom: document.getElementById('action-trace-from'),
    actionImpactFrom: document.getElementById('action-impact-from'),
    btnPreviewSource: document.getElementById('btn-preview-source'),
    sourcePreviewContainer: document.getElementById('source-preview-container'),
    sourcePreviewFile: document.getElementById('source-preview-file'),
    sourcePreviewLang: document.getElementById('source-preview-lang'),
    sourcePreviewCode: document.getElementById('source-preview-code'),
    closeSourcePreviewBtn: document.getElementById('close-source-preview-btn'),
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

    // Indexing Dashboard
    indexingDashboard: document.getElementById('indexing-progress-dashboard'),
    progressTierTitle: document.getElementById('progress-current-tier-title'),
    progressElapsedTimer: document.getElementById('progress-elapsed-timer'),
    progressHeartbeatBadge: document.getElementById('progress-heartbeat-badge'),
    indexingProgressBar: document.getElementById('indexing-progress-bar'),
    stepperTier1: document.getElementById('stepper-tier-1'),
    stepperTier2: document.getElementById('stepper-tier-2'),
    stepperTier3: document.getElementById('stepper-tier-3'),
    stepperStatus1: document.getElementById('stepper-status-1'),
    stepperStatus2: document.getElementById('stepper-status-2'),
    stepperStatus3: document.getElementById('stepper-status-3'),

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
    if (type === 'error') {
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
    } else {
        toast.setAttribute('role', 'status');
        toast.setAttribute('aria-live', 'polite');
    }

    let icon = '';
    if (type === 'success') {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>`;
    } else if (type === 'error') {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>`;
    } else {
        icon = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>`;
    }

    toast.innerHTML = `${icon}<span>${escapeHtml(message)}</span>`;
    const dismiss = document.createElement('button');
    dismiss.type = 'button';
    dismiss.className = 'toast-dismiss';
    dismiss.setAttribute('aria-label', 'Dismiss notification');
    dismiss.textContent = '×';
    const removeToast = () => {
        toast.classList.add('toast-exit');
        setTimeout(() => { toast.remove(); }, 200);
    };
    dismiss.addEventListener('click', removeToast);
    toast.appendChild(dismiss);
    els.toastContainer.appendChild(toast);

    const ttl = type === 'error' ? 15000 : 3000;
    setTimeout(removeToast, ttl);
}

// ==========================================================================
// App Initialization
// ==========================================================================

function initReducedMotionWatcher() {
    if (!window.matchMedia) return;
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const apply = () => {
        state.prefersReducedMotion = !!mq.matches;
        if (state.prefersReducedMotion && state.graph3d) {
            state.isAutoRotating = false;
            if (els.autoRotateBtn) els.autoRotateBtn.classList.remove('active');
            state.graph3d.controls().autoRotate = false;
            state.graph3d.linkDirectionalParticles(() => 0);
        }
    };
    if (mq.addEventListener) mq.addEventListener('change', apply);
    else if (mq.addListener) mq.addListener(apply);
}

function init() {
    initReducedMotionWatcher();
    if (els.projectInput) els.projectInput.value = state.currentProject;
    if (els.projectPathText && state.currentProject) {
        const parts = state.currentProject.replace(/[\/\\]+$/, '').split(/[\/\\]/);
        els.projectPathText.textContent = parts[parts.length - 1] || state.currentProject;
        els.projectPathText.title = state.currentProject;
    }
    if (els.uiTokenInput) els.uiTokenInput.value = state.uiToken;
    if (els.useLlm) els.useLlm.checked = state.useLlm;
    updateAiDisclosure();
    updateIndexingDependencies();
    renderRecentProjects();
    checkLlmStatus();

    updateProjectLabel();
    init3DGraph();
    setupEventListeners();
    closeAllPopovers();
    if (els.contextPanel) els.contextPanel.setAttribute('inert', '');
    if (els.drawerToggle) els.drawerToggle.setAttribute('aria-expanded', 'false');
    if (els.readyBadge) {
        els.readyBadge.setAttribute(
            'aria-label',
            `Engine status: ${(els.readyBadgeText && els.readyBadgeText.textContent) || 'Not indexed'}`
        );
    }

    window.addEventListener('beforeunload', (e) => {
        if (state.indexingAbort && !state._indexingDone) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    if (state.currentProject) {
        loadProject();
    } else {
        showWelcomeOverlay();
        openFolderBrowser();
    }
    
    initOnboardingTour();
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
                <div class="welcome-step"><span class="step-num">1</span> Browse to select your local repository</div>
                <div class="welcome-step"><span class="step-num">2</span> Click any node to inspect it</div>
                <div class="welcome-step"><span class="step-num">3</span> Search, query, trace, or analyze impact</div>
            </div>
            <div class="welcome-actions">
                <button class="btn-welcome-sample" id="welcome-open-btn">Browse for Repository</button>
            </div>
            <p class="welcome-shortcut">Press <kbd>/</kbd> to search · <kbd>P</kbd> to switch projects</p>
        </div>
    `);
    container.appendChild(overlay);
    const openBtn = document.getElementById('welcome-open-btn');
    if (openBtn) {
        openBtn.addEventListener('click', () => {
            overlay.remove();
            openFolderBrowser();
        });
    }
}

function getProjectShortName(path) {
    if (!path) return 'Repository';
    const clean = path.replace(/[/\\]+$/, '');
    const parts = clean.split(/[/\\]/);
    return parts[parts.length - 1] || clean;
}

function updateProjectLabel() {
    if (!els.currentProjectLabel) return;
    if (state.currentProject) {
        const name = getProjectShortName(state.currentProject);
        els.currentProjectLabel.textContent = name;
        els.currentProjectLabel.title = state.currentProject;
    } else {
        els.currentProjectLabel.textContent = 'Select Project…';
        els.currentProjectLabel.title = 'Click to choose repository';
    }
}

function closeAllPopovers(options) {
    const restoreFocus = !options || options.restoreFocus !== false;
    const popovers = [
        els.projectPopover,
        els.layersPopover,
        els.indexPopover,
        els.searchModeDropdown,
        els.searchResultsDropdown,
    ];
    popovers.forEach((el) => {
        if (!el) return;
        el.classList.add('closed');
        el.setAttribute('inert', '');
    });
    if (els.contextPanel && els.contextPanel.classList.contains('closed')) {
        els.contextPanel.setAttribute('inert', '');
    }
    // Update ARIA expanded state on trigger buttons
    if (els.projectPillBtn) els.projectPillBtn.setAttribute('aria-expanded', 'false');
    if (els.layersToggleBtn) els.layersToggleBtn.setAttribute('aria-expanded', 'false');
    if (els.headerIndexBtn) els.headerIndexBtn.setAttribute('aria-expanded', 'false');
    if (restoreFocus && state.lastPopoverTrigger && typeof state.lastPopoverTrigger.focus === 'function') {
        state.lastPopoverTrigger.focus();
    }
    state.lastPopoverTrigger = null;
}

function focusFirstFocusable(container) {
    if (!container) return;
    const focusable = container.querySelector(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    if (focusable) focusable.focus();
}

function openPopover(popover, trigger) {
    if (!popover) return;
    closeAllPopovers({ restoreFocus: false });
    state.lastPopoverTrigger = trigger || null;
    popover.classList.remove('closed');
    popover.removeAttribute('inert');
    if (trigger) trigger.setAttribute('aria-expanded', 'true');
    focusFirstFocusable(popover);
}

function updateAiDisclosure() {
    const el = document.getElementById('ai-disclosure');
    if (!el) return;
    el.hidden = !state.useLlm;
}

function persistUseLlmFromInput() {
    if (!els.useLlm) return;
    state.useLlm = !!els.useLlm.checked;
    localStorage.setItem('ckc_use_llm', state.useLlm ? '1' : '0');
    updateAiDisclosure();
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

function getLinkRelationColor(relation) {
    if (!relation) return 'rgba(255, 255, 255, 0.15)';
    const rel = relation.toLowerCase();
    if (rel === 'calls' || rel === 'call' || rel === 'indirect_call') return '#38bdf8'; // Sky blue
    if (rel === 'imports' || rel === 'imports_from' || rel === 'import') return '#a78bfa'; // Violet
    if (rel === 'defines' || rel === 'contains' || rel === 'method' || rel === 'defined_in') return '#34d399'; // Emerald
    if (rel === 'inherits' || rel === 'extends' || rel === 'mixes_in') return '#fbbf24'; // Amber
    return 'rgba(255, 255, 255, 0.15)';
}

function init3DGraph() {
    if (!els.container3d || !window.ForceGraph3D) return;

    const graphBg = getComputedStyle(document.documentElement)
        .getPropertyValue('--bg-base')
        .trim() || '#0c0e14';

    state.graph3d = ForceGraph3D()(els.container3d)
        .backgroundColor(graphBg)
        .showNavInfo(false)
        .nodeRelSize(4)
        .nodeResolution(16)
        .nodeVal(node => Math.max(3, Math.sqrt(node.degree || 1) * 2.2 + 2.5))
        .nodeColor(node => {
            if (node.__impactTarget) return '#ef4444';
            if (node.__impacted) return '#f59e0b';
            if (node.__tracePath) return '#38bdf8';
            if (state.selectedNode) {
                if (node.id === state.selectedNode.id) return '#f43f5e';
                if (state.incomingCallers && state.incomingCallers.has(node.id)) return '#38bdf8';
                if (state.outgoingCallees && state.outgoingCallees.has(node.id)) return '#f59e0b';
                return 'rgba(255, 255, 255, 0.08)';
            }
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
            const kind = node.kind ? ` &bull; ${escapeHtml(node.kind)}` : '';
            const callers = node.in_degree != null ? ` &bull; ${node.in_degree} in` : '';
            const callees = node.out_degree != null ? ` &bull; ${node.out_degree} out` : '';
            return `<div style="background:#131620;border:1px solid rgba(255,255,255,0.14);border-radius:6px;padding:6px 10px;font-family:'IBM Plex Sans',sans-serif;box-shadow:0 4px 16px rgba(0,0,0,0.5);">
                <div style="font-weight:700;font-size:13px;color:#f3f4f6;font-family:'JetBrains Mono',monospace;">${escapeHtml(node.label || node.id)}</div>
                <div style="font-size:11px;color:#9ca3af;margin-top:2px;">${cat}${kind} &bull; ${node.degree || 0} total${callers}${callees}</div>
            </div>`;
        })
        .nodeOpacity(0.95)
        .linkColor(link => {
            if (link.__highlight) return '#38bdf8';
            if (link.__trace) return '#38bdf8';
            if (link.__impact) return '#ef4444';
            if (state.selectedNode) {
                const s = typeof link.source === 'object' ? link.source.id : link.source;
                const t = typeof link.target === 'object' ? link.target.id : link.target;
                if (t === state.selectedNode.id) return '#38bdf8';
                if (s === state.selectedNode.id) return '#f59e0b';
                return 'rgba(255, 255, 255, 0.03)';
            }
            if (state.highlightNodes.size > 0) return 'rgba(255, 255, 255, 0.03)';
            return getLinkRelationColor(link.relation);
        })
        .linkWidth(link => {
            if (link.__highlight || link.__trace || link.__impact) return 2.5;
            if (state.selectedNode) {
                const s = typeof link.source === 'object' ? link.source.id : link.source;
                const t = typeof link.target === 'object' ? link.target.id : link.target;
                if (s === state.selectedNode.id || t === state.selectedNode.id) return 2.2;
            }
            return 0.8;
        })
        .linkDirectionalArrowLength(link => {
            if (state.highlightNodes.size > 0 && !link.__highlight && !link.__trace && !link.__impact) return 0;
            return 3.5;
        })
        .linkDirectionalArrowRelPos(1)
        .linkDirectionalArrowColor(link => {
            if (link.__trace) return '#38bdf8';
            if (link.__impact) return '#ef4444';
            if (state.selectedNode) {
                const s = typeof link.source === 'object' ? link.source.id : link.source;
                const t = typeof link.target === 'object' ? link.target.id : link.target;
                if (t === state.selectedNode.id) return '#38bdf8';
                if (s === state.selectedNode.id) return '#f59e0b';
            }
            return getLinkRelationColor(link.relation);
        })
        .linkDirectionalParticles(link => {
            if (state.prefersReducedMotion) return 0;
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

function setLayoutMode(mode) {
    if (!state.graph3d) return;
    state.layoutMode = mode;

    [els.mode3dBtn, els.mode2dBtn, els.modeDagBtn].forEach(btn => {
        if (btn) btn.classList.toggle('active', btn.dataset.mode === mode);
    });

    if (mode === '2d') {
        state.graph3d.numDimensions(2);
        state.graph3d.dagMode(null);
        state.graph3d.cameraPosition({ x: 0, y: 0, z: 280 }, { x: 0, y: 0, z: 0 }, motionMs(700));
        showToast('Switched to 2D Planar Map', 'info');
    } else if (mode === 'dag') {
        state.graph3d.numDimensions(3);
        state.graph3d.dagMode('td');
        state.graph3d.dagLevelDistance(65);
        state.graph3d.cameraPosition({ x: 0, y: -40, z: 320 }, { x: 0, y: 0, z: 0 }, motionMs(700));
        showToast('Switched to Hierarchical Top-Down DAG', 'info');
    } else {
        state.graph3d.numDimensions(3);
        state.graph3d.dagMode(null);
        state.graph3d.cameraPosition({ x: 0, y: 0, z: 280 }, { x: 0, y: 0, z: 0 }, motionMs(700));
        showToast('Switched to 3D Force Graph', 'info');
    }

    if (typeof state.graph3d.d3ReheatSimulation === 'function') {
        state.graph3d.d3ReheatSimulation();
    }
}
window.setLayoutMode = setLayoutMode;

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
        motionMs(800)
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
            if (isOpen) {
                closeAllPopovers();
            } else {
                openPopover(els.projectPopover, els.projectPillBtn);
            }
        });
    }
    if (els.closeProjectPopoverBtn) {
        els.closeProjectPopoverBtn.addEventListener('click', () => {
            closeAllPopovers();
        });
    }

    if (els.layersToggleBtn && els.layersPopover) {
        els.layersToggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.layersPopover.classList.contains('closed');
            if (isOpen) {
                closeAllPopovers();
            } else {
                openPopover(els.layersPopover, els.layersToggleBtn);
            }
        });
    }
    if (els.closeLayersPopoverBtn) {
        els.closeLayersPopoverBtn.addEventListener('click', () => {
            closeAllPopovers();
        });
    }

    if (els.headerIndexBtn && els.indexPopover) {
        els.headerIndexBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            if (isOpen) {
                closeAllPopovers();
            } else {
                openPopover(els.indexPopover, els.headerIndexBtn);
            }
        });
    }
    if (els.readyBadge && els.indexPopover) {
        els.readyBadge.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.indexPopover.classList.contains('closed');
            if (isOpen) {
                closeAllPopovers();
            } else {
                openPopover(els.indexPopover, els.readyBadge);
            }
        });
    }
    if (els.closeIndexPopoverBtn) {
        els.closeIndexPopoverBtn.addEventListener('click', () => {
            closeAllPopovers();
        });
    }

    // Search Mode Button & Dropdown
    if (els.searchModeBtn && els.searchModeDropdown) {
        els.searchModeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = !els.searchModeDropdown.classList.contains('closed');
            if (isOpen) {
                closeAllPopovers();
            } else {
                openPopover(els.searchModeDropdown, els.searchModeBtn);
            }
        });

        els.searchModeDropdown.querySelectorAll('.mode-option').forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const mode = opt.dataset.mode;
                setSearchMode(mode);
                closeAllPopovers();
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
        const val = (els.projectInput ? els.projectInput.value : '').trim();
        if (!val) {
            openFolderBrowser();
            return;
        }
        persistUiTokenFromInput();
        state.currentProject = val;
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
        els.autoRotateBtn.setAttribute('aria-pressed', 'false');
        els.autoRotateBtn.addEventListener('click', () => {
            state.isAutoRotating = !state.isAutoRotating;
            els.autoRotateBtn.classList.toggle('active', state.isAutoRotating);
            els.autoRotateBtn.setAttribute('aria-pressed', state.isAutoRotating ? 'true' : 'false');
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

    // Layout Mode Switcher Buttons
    if (els.mode3dBtn) els.mode3dBtn.addEventListener('click', () => setLayoutMode('3d'));
    if (els.mode2dBtn) els.mode2dBtn.addEventListener('click', () => setLayoutMode('2d'));
    if (els.modeDagBtn) els.modeDagBtn.addEventListener('click', () => setLayoutMode('dag'));

    // Entity Filters & Noise Reduction
    if (els.filterHideVendor) {
        els.filterHideVendor.addEventListener('change', (e) => {
            state.filters.hideVendor = e.target.checked;
            applyFilters();
        });
    }

    ['code', 'doc', 'schema', 'test'].forEach(cat => {
        const checkbox = els[`filter${cat.charAt(0).toUpperCase() + cat.slice(1)}`];
        if (checkbox) {
            checkbox.addEventListener('change', (e) => {
                state.filters[cat] = e.target.checked;
                applyFilters();
            });
        }
    });

    ['Calls', 'Imports', 'Defines', 'Inherits'].forEach(rel => {
        const checkbox = els[`filterRel${rel}`];
        if (checkbox) {
            checkbox.addEventListener('change', (e) => {
                state.filters[`rel${rel}`] = e.target.checked;
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

    if (els.actionFocusNode) {
        els.actionFocusNode.addEventListener('click', () => {
            if (state.selectedNode && state.graph3d) {
                const gNodes = state.graph3d.graphData().nodes;
                const targetNode = gNodes.find(n => n.id === state.selectedNode.id);
                if (targetNode) flyToNode(targetNode);
            }
        });
    }

    if (els.actionTraceFrom) {
        els.actionTraceFrom.addEventListener('click', () => {
            if (state.selectedNode) enterTraceMode(state.selectedNode);
        });
    }

    if (els.actionImpactFrom) {
        els.actionImpactFrom.addEventListener('click', () => {
            if (state.selectedNode) runImpact(state.selectedNode.label || state.selectedNode.id);
        });
    }

    if (els.btnPreviewSource) {
        els.btnPreviewSource.addEventListener('click', toggleSourcePreview);
    }

    if (els.closeSourcePreviewBtn) {
        els.closeSourcePreviewBtn.addEventListener('click', closeSourcePreview);
    }

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
    els.drawerToggle.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            els.drawerToggle.click();
        }
    });
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
            if (els.folderBrowserDialog && els.folderBrowserDialog.open) {
                closeFolderBrowser();
                return;
            }
            if (els.byokDialog && els.byokDialog.open) {
                closeByokDialog();
                return;
            }
            if (state.isTraceMode) {
                exitTraceMode();
            } else {
                closeAllPopovers();
                clearSelection();
                clearOverlays();
                if (els.contextPanel) {
                    els.contextPanel.classList.add('closed');
                    els.contextPanel.setAttribute('inert', '');
                }
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
        } else if (e.key === '?' && !isInput) {
            e.preventDefault();
            startOnboardingTour(true);
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

    // Folder Browser
    if (els.browseBtn) {
        els.browseBtn.addEventListener('click', openFolderBrowser);
    }
    if (els.browserSelectBtn) {
        els.browserSelectBtn.addEventListener('click', confirmFolderSelection);
    }
    if (els.browserCancelBtn) {
        els.browserCancelBtn.addEventListener('click', closeFolderBrowser);
    }
    if (els.browserCloseBtn) {
        els.browserCloseBtn.addEventListener('click', closeFolderBrowser);
    }
    if (els.browserQuickHome) {
        els.browserQuickHome.addEventListener('click', () => navigateBrowserTo(null));
    }
    if (els.browserQuickRoot) {
        els.browserQuickRoot.addEventListener('click', () => navigateBrowserTo('/'));
    }
    if (els.folderBrowserDialog) {
        els.folderBrowserDialog.addEventListener('click', (e) => {
            const rect = els.folderBrowserDialog.getBoundingClientRect();
            const isInDialog = (
                rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
                rect.left <= e.clientX && e.clientX <= rect.left + rect.width
            );
            if (!isInDialog) {
                closeFolderBrowser();
            }
        });
        els.folderBrowserDialog.addEventListener('cancel', (e) => {
            e.preventDefault();
            closeFolderBrowser();
        });
    }

    // BYOK Provider Dialog
    if (els.headerAiBtn) {
        els.headerAiBtn.addEventListener('click', openByokDialog);
    }
    if (els.llmChip) {
        els.llmChip.addEventListener('click', openByokDialog);
    }
    if (els.openByokFromIndexBtn) {
        els.openByokFromIndexBtn.addEventListener('click', () => {
            closeAllPopovers();
            openByokDialog();
        });
    }
    if (els.byokCloseBtn) {
        els.byokCloseBtn.addEventListener('click', closeByokDialog);
    }
    if (els.byokCancelBtn) {
        els.byokCancelBtn.addEventListener('click', closeByokDialog);
    }
    if (els.byokSaveBtn) {
        els.byokSaveBtn.addEventListener('click', saveByokConfig);
    }
    if (els.byokSkipBtn) {
        els.byokSkipBtn.addEventListener('click', skipByok);
    }
    if (els.byokRetryBtn) {
        els.byokRetryBtn.addEventListener('click', () => probeByokProvider());
    }
    if (els.byokToggleKey && els.byokApiKey) {
        els.byokToggleKey.addEventListener('click', () => {
            const isPw = els.byokApiKey.type === 'password';
            els.byokApiKey.type = isPw ? 'text' : 'password';
            els.byokToggleKey.textContent = isPw ? '🔒' : '👁';
        });
    }
    if (els.byokModelSelect) {
        els.byokModelSelect.addEventListener('change', () => {
            if (els.byokModelSelect.value === '__custom__') {
                if (els.byokModelCustom) els.byokModelCustom.classList.remove('hidden');
            } else {
                if (els.byokModelCustom) els.byokModelCustom.classList.add('hidden');
            }
        });
    }
    document.querySelectorAll('.provider-pill').forEach(pill => {
        pill.addEventListener('click', () => {
            const provider = pill.dataset.provider;
            selectProviderPreset(provider);
        });
    });
    if (els.byokDialog) {
        els.byokDialog.addEventListener('click', (e) => {
            const rect = els.byokDialog.getBoundingClientRect();
            const isInDialog = (
                rect.top <= e.clientY && e.clientY <= rect.top + rect.height &&
                rect.left <= e.clientX && e.clientX <= rect.left + rect.width
            );
            if (!isInDialog) {
                closeByokDialog();
            }
        });
        els.byokDialog.addEventListener('cancel', (e) => {
            e.preventDefault();
            closeByokDialog();
        });
    }

    // Recent Projects
    if (els.clearRecentProjectsBtn) {
        els.clearRecentProjectsBtn.addEventListener('click', clearRecentProjects);
    }

    // Indexing Option Dependencies
    if (els.useLlm) {
        els.useLlm.addEventListener('change', () => {
            persistUseLlmFromInput();
            updateIndexingDependencies();
        });
    }

    // Help Tour
    if (els.helpTourBtn) {
        els.helpTourBtn.addEventListener('click', () => {
            startOnboardingTour(true);
        });
    }
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
            const active = opt.dataset.mode === mode;
            opt.classList.toggle('active', active);
            opt.setAttribute('aria-selected', active ? 'true' : 'false');
        });
    }

    if (mode === 'query') {
        els.commandBar.placeholder = 'Ask a question about codebase architecture...';
    } else if (mode === 'impact') {
        els.commandBar.placeholder = 'Enter symbol for impact analysis (e.g. AuthService)...';
    } else if (mode === 'trace') {
        els.commandBar.placeholder = 'Enter flow trace: symbolA → symbolB...';
    } else {
        els.commandBar.placeholder = 'Search symbols, ask a question, or A → B to trace';
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
            const item = document.createElement('button');
            item.type = 'button';
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

    const actionImpact = document.createElement('button');
    actionImpact.type = 'button';
    actionImpact.className = 'search-action-btn';
    actionImpact.innerHTML = `
        <svg class="search-action-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path></svg>
        <span>Analyze impact for <strong>"${escapeHtml(query)}"</strong></span>
    `;
    actionImpact.addEventListener('click', () => {
        closeAllPopovers();
        runImpact(query);
    });
    els.searchActionsBar.appendChild(actionImpact);

    const actionQuery = document.createElement('button');
    actionQuery.type = 'button';
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

function motionMs(preferred) {
    return state.prefersReducedMotion ? 0 : preferred;
}

function fitGraphView() {
    if (state.graph3d) {
        state.graph3d.zoomToFit(motionMs(800), 40);
    }
}

function resetCameraView() {
    if (state.graph3d) {
        state.graph3d.cameraPosition({ x: 0, y: 0, z: 300 }, { x: 0, y: 0, z: 0 }, motionMs(800));
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
    document.getElementById('unindexed-overlay')?.remove();
    document.getElementById('graph-legend')?.classList.remove('hidden');

    persistUiTokenFromInput();
    setBusy(true);
    try {
        const statusRes = await apiFetch(`/api/status?project=${encodeURIComponent(state.currentProject)}`);
        updateStatus(statusRes);

        const isGraphIndexed = !!statusRes.status?.graphify?.indexed;
        if (!isGraphIndexed) {
            addRecentProject(state.currentProject, { indexed: false });
            document.getElementById('graph-legend')?.classList.add('hidden');
            showUnindexedPrompt(state.currentProject, statusRes);
            showToast(`Repository selected: ${getProjectShortName(state.currentProject)}. Run indexing to build the knowledge graph.`, 'info');
            return;
        }

        const graphRes = await apiFetch(`/api/graph?project=${encodeURIComponent(state.currentProject)}`);
        renderGraph(graphRes);
        addRecentProject(state.currentProject, {
            indexed: true,
            nodeCount: graphRes.meta?.node_count || 0,
            edgeCount: graphRes.meta?.edge_count || 0,
        });
        showToast(`Loaded ${state.currentProjectLabel ? state.currentProjectLabel.textContent : 'project'} (${graphRes.meta?.node_count || 0} symbols)`, 'success');
    } catch (e) {
        if (e.message && e.message.includes('not yet indexed')) {
            addRecentProject(state.currentProject, { indexed: false });
            document.getElementById('graph-legend')?.classList.add('hidden');
            showUnindexedPrompt(state.currentProject);
            showToast('Codebase not yet indexed. Run indexing to build the knowledge graph.', 'info');
            return;
        }
        console.error('Failed to load project:', e);
        els.readyBadge.className = 'badge-status badge-error';
        if (els.readyBadgeText) els.readyBadgeText.textContent = 'Error';
        if (els.readyBadge) els.readyBadge.setAttribute('aria-label', 'Engine status: Error');
        showToast(`Failed to load project: ${e.message}`, 'error');
        setSafeHtml(
            els.resultsOutput,
            `<span style="color:var(--accent-rose)">Error loading project: ${escapeHtml(e.message)}</span>`
        );
    } finally {
        setBusy(false);
    }
}

function showUnindexedPrompt(projectPath, statusRes) {
    const container = els.container3d || document.getElementById('graph-3d');
    if (!container) return;
    document.getElementById('unindexed-overlay')?.remove();
    document.getElementById('welcome-overlay')?.remove();

    const shortName = getProjectShortName(projectPath);
    const overlay = document.createElement('div');
    overlay.id = 'unindexed-overlay';
    overlay.className = 'unindexed-overlay';
    overlay.innerHTML = DOMPurify.sanitize(`
        <div class="unindexed-card">
            <div class="unindexed-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                </svg>
            </div>
            <h2 class="unindexed-title">Codebase Not Yet Indexed</h2>
            <div class="unindexed-repo-tag">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
                <span>${escapeHtml(shortName)}</span>
            </div>
            <p class="unindexed-desc">
                This repository has been selected, but its 3-tier knowledge graph has not been built yet. Start indexing to explore architecture, AST execution flows, and symbol dependencies.
            </p>
            <div class="unindexed-actions">
                <button type="button" class="btn btn-primary btn-lg" id="unindexed-start-btn">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                    </svg>
                    <span>Start Indexing</span>
                </button>
                <button type="button" class="btn btn-secondary" id="unindexed-change-btn">Select Other Folder</button>
            </div>
        </div>
    `);
    container.appendChild(overlay);

    document.getElementById('unindexed-start-btn')?.addEventListener('click', () => {
        overlay.remove();
        runIndexing();
    });

    document.getElementById('unindexed-change-btn')?.addEventListener('click', () => {
        openFolderBrowser();
    });
}

function updateStatus(res) {
    if (res.status && res.status.all_ready) {
        els.readyBadge.className = 'badge-status badge-ready';
        if (els.readyBadgeText) els.readyBadgeText.textContent = '3 of 3 tiers ready';
    } else {
        const count = res.status?.ready_count ?? 0;
        els.readyBadge.className = 'badge-status';
        if (els.readyBadgeText) {
            els.readyBadgeText.textContent = count
                ? `${count} of 3 tiers ready`
                : 'Not indexed';
        }
    }
    if (els.readyBadge && els.readyBadgeText) {
        els.readyBadge.setAttribute('aria-label', `Engine status: ${els.readyBadgeText.textContent}`);
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

    // Apply filtering and render into 3D / 2D / DAG
    applyFilters();
    setTimeout(() => { fitGraphView(); }, 600);
}

function renderCommunityList(communities) {
    if (!els.communityList) return;
    els.communityList.innerHTML = '';
    if (els.commTotalBadge) els.commTotalBadge.textContent = `${communities.length} clusters`;

    communities.forEach(c => {
        const li = document.createElement('li');
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'community-item';
        const color = getNodeCommunityColor(c.id);
        const samples = (c.sample_labels || []).slice(0, 2).join(', ');
        const title = `Cluster ${c.id}${samples ? ` • ${samples}` : ''}`;

        const swatch = document.createElement('span');
        swatch.className = 'comm-swatch';
        swatch.style.backgroundColor = color;
        const titleEl = document.createElement('span');
        titleEl.className = 'comm-title';
        titleEl.textContent = title;
        const sizeEl = document.createElement('span');
        sizeEl.className = 'comm-size';
        sizeEl.textContent = String(c.size);
        btn.appendChild(swatch);
        btn.appendChild(titleEl);
        btn.appendChild(sizeEl);
        btn.addEventListener('click', () => {
            zoomToCommunity(c.id);
            closeAllPopovers();
        });
        li.appendChild(btn);
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
        motionMs(900)
    );
}

function applyFilters() {
    if (!state.graphData) return;
    const rawNodes = (state.graphData.elements.nodes || []).map(n => n.data);
    const rawLinks = (state.graphData.elements.edges || []).map(e => e.data);

    const visibleNodes = rawNodes.filter(n => {
        // Noise reduction filter for vendor/generated/node_modules/dist files
        if (state.filters.hideVendor && n.is_vendor) return false;
        // Entity category filter
        return state.filters[n.category || 'code'] !== false;
    });
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id));

    const cleanLinks = rawLinks.map(l => {
        const sId = typeof l.source === 'object' ? l.source.id : l.source;
        const tId = typeof l.target === 'object' ? l.target.id : l.target;
        return Object.assign({}, l, { source: sId, target: tId });
    }).filter(l => {
        if (!visibleNodeIds.has(l.source) || !visibleNodeIds.has(l.target)) return false;

        const rel = (l.relation || '').toLowerCase();
        if (rel === 'calls' || rel === 'call' || rel === 'indirect_call') {
            if (state.filters.relCalls === false) return false;
        } else if (rel === 'imports' || rel === 'imports_from' || rel === 'import') {
            if (state.filters.relImports === false) return false;
        } else if (rel === 'defines' || rel === 'contains' || rel === 'method' || rel === 'defined_in') {
            if (state.filters.relDefines === false) return false;
        } else if (rel === 'inherits' || rel === 'extends' || rel === 'mixes_in') {
            if (state.filters.relInherits === false) return false;
        }
        return true;
    });

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
        state.incomingCallers = new Set();
        state.outgoingCallees = new Set();

        gLinks.forEach(link => {
            const s = typeof link.source === 'object' ? link.source.id : link.source;
            const t = typeof link.target === 'object' ? link.target.id : link.target;
            if (t === data.id) {
                neighbors.add(s);
                state.incomingCallers.add(s);
                link.__highlight = true;
            } else if (s === data.id) {
                neighbors.add(t);
                state.outgoingCallees.add(t);
                link.__highlight = true;
            } else {
                link.__highlight = false;
            }
        });

        state.highlightNodes = neighbors;
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalArrowLength(state.graph3d.linkDirectionalArrowLength());

        if (targetNode) flyToNode(targetNode);
    }

    showContextPanel(data);
}

function clearSelection() {
    state.selectedNode = null;
    state.highlightNodes.clear();
    state.incomingCallers = new Set();
    state.outgoingCallees = new Set();

    if (state.graph3d) {
        state.graph3d.graphData().links.forEach(l => { l.__highlight = false; });
        state.graph3d.nodeColor(state.graph3d.nodeColor());
        state.graph3d.linkColor(state.graph3d.linkColor());
        state.graph3d.linkWidth(state.graph3d.linkWidth());
        state.graph3d.linkDirectionalArrowLength(state.graph3d.linkDirectionalArrowLength());
    }

    els.contextPanel.classList.add('closed');
    els.contextPanel.setAttribute('inert', '');
    closeSourcePreview();
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
    els.contextPanel.removeAttribute('inert');

    const label = data.label || data.id;
    els.nodeLabel.textContent = label;
    const cat = (data.category || 'code').toLowerCase();
    els.nodeCategory.textContent = cat.charAt(0).toUpperCase() + cat.slice(1);

    let typeLabel = data.kind ? (data.kind.charAt(0).toUpperCase() + data.kind.slice(1)) : 'Symbol';
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

    closeSourcePreview();

    // Group incoming callers vs outgoing dependencies
    const incoming = [];
    const outgoing = [];
    if (state.graphData && state.graphData.elements.edges) {
        state.graphData.elements.edges.forEach(edge => {
            const e = edge.data;
            const sId = typeof e.source === 'object' ? e.source.id : e.source;
            const tId = typeof e.target === 'object' ? e.target.id : e.target;
            if (tId === data.id) {
                incoming.push({ id: sId, rel: e.relation || 'references' });
            } else if (sId === data.id) {
                outgoing.push({ id: tId, rel: e.relation || 'uses' });
            }
        });
    }

    const inCount = data.in_degree != null ? data.in_degree : incoming.length;
    const outCount = data.out_degree != null ? data.out_degree : outgoing.length;

    if (els.nodeInDegree) els.nodeInDegree.textContent = inCount;
    if (els.nodeOutDegree) els.nodeOutDegree.textContent = outCount;
    els.nodeDegree.textContent = (inCount + outCount) || data.degree || 0;

    // Render grouped connections
    els.nodeConnections.innerHTML = '';
    if (incoming.length === 0 && outgoing.length === 0) {
        els.nodeConnections.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:4px 0;">No direct connections recorded.</div>';
    } else {
        if (incoming.length > 0) {
            const inSec = renderConnectionSection(`Incoming Callers & References (${incoming.length})`, incoming, 'in');
            els.nodeConnections.appendChild(inSec);
        }
        if (outgoing.length > 0) {
            const outSec = renderConnectionSection(`Outgoing Calls & Dependencies (${outgoing.length})`, outgoing, 'out');
            els.nodeConnections.appendChild(outSec);
        }
    }
}

function renderConnectionSection(title, items, dir) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'conn-group';

    const header = document.createElement('div');
    header.className = 'conn-group-header';
    header.textContent = title;
    groupDiv.appendChild(header);

    const chipsDiv = document.createElement('div');
    chipsDiv.className = 'conn-chips';

    items.slice(0, 16).forEach(item => {
        const a = document.createElement('a');
        a.className = 'symbol-link';
        let friendly = item.id;
        if (state.graphData) {
            const found = state.graphData.elements.nodes.find(n => n.data.id === item.id);
            if (found && found.data.label) friendly = found.data.label;
        }
        const dirArrow = dir === 'in' ? '←' : '→';
        a.innerHTML = `<span class="rel-tag">${dirArrow} ${escapeHtml(item.rel)}</span> <span>${escapeHtml(friendly)}</span>`;
        a.onclick = () => selectNodeByLabel(friendly);
        chipsDiv.appendChild(a);
    });

    if (items.length > 16) {
        const more = document.createElement('span');
        more.className = 'conn-more-count';
        more.textContent = `+${items.length - 16} more`;
        chipsDiv.appendChild(more);
    }

    groupDiv.appendChild(chipsDiv);
    return groupDiv;
}

async function toggleSourcePreview() {
    if (!state.selectedNode || !els.sourcePreviewContainer) return;
    const isVisible = !els.sourcePreviewContainer.classList.contains('hidden');
    if (isVisible) {
        closeSourcePreview();
        return;
    }

    const node = state.selectedNode;
    const file = node.source_file;
    if (!file) {
        showToast('No source file location available for this node', 'info');
        return;
    }

    let line = 1;
    if (node.source_location) {
        const parsed = parseInt(String(node.source_location).split(/[-:,]/)[0], 10);
        if (!isNaN(parsed) && parsed > 0) line = parsed;
    }

    els.sourcePreviewContainer.classList.remove('hidden');
    if (els.sourcePreviewFile) els.sourcePreviewFile.textContent = file;
    if (els.sourcePreviewLang) els.sourcePreviewLang.textContent = node.file_type || 'code';
    if (els.sourcePreviewCode) {
        els.sourcePreviewCode.innerHTML = '<div style="color:var(--text-muted);padding:8px;">Loading source snippet...</div>';
    }

    try {
        const queryParams = new URLSearchParams({
            project: state.currentProject,
            file: file,
            line: String(line),
            window: '30'
        });
        const data = await apiFetch(`/api/source?${queryParams.toString()}`);
        renderSourceSnippet(data);
    } catch (err) {
        console.error('Failed to load source snippet:', err);
        if (els.sourcePreviewCode) {
            els.sourcePreviewCode.innerHTML = `<div style="color:var(--accent-rose);padding:8px;">Failed to load source: ${escapeHtml(err.message)}</div>`;
        }
    }
}

function renderSourceSnippet(data) {
    if (!els.sourcePreviewCode) return;
    if (els.sourcePreviewLang) els.sourcePreviewLang.textContent = data.language || 'code';
    if (els.sourcePreviewFile) els.sourcePreviewFile.textContent = `${data.file}:${data.highlight_line || data.start_line}`;

    const lines = data.lines || [];
    const highlightLine = data.highlight_line;

    let html = '';
    lines.forEach(item => {
        const lineNum = typeof item === 'object' && item !== null ? item.line_num : '';
        const codeText = typeof item === 'object' && item !== null ? item.code : item;
        const isTarget = lineNum === highlightLine;
        const cls = isTarget ? 'source-line highlight' : 'source-line';
        html += `<div class="${cls}">` +
            `<span class="source-line-num">${lineNum}</span>` +
            `<span class="source-line-code">${escapeHtml(codeText)}</span>` +
            `</div>`;
    });
    els.sourcePreviewCode.innerHTML = html;

    setTimeout(() => {
        const targetEl = els.sourcePreviewCode.querySelector('.source-line.highlight');
        if (targetEl) {
            targetEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
        }
    }, 50);
}

function closeSourcePreview() {
    if (els.sourcePreviewContainer) {
        els.sourcePreviewContainer.classList.add('hidden');
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
        if (state.useLlm && els.resultsOutput) {
            const badge = document.createElement('div');
            badge.className = 'ai-synthesis-badge';
            badge.textContent = 'AI synthesis';
            badge.setAttribute('role', 'status');
            els.resultsOutput.prepend(badge);
        }
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
                    if (window.DOMPurify && typeof DOMPurify.sanitize === 'function') {
                        container.innerHTML = DOMPurify.sanitize(svg, {
                            USE_PROFILES: { svg: true, svgFilters: true },
                        });
                    } else {
                        container.textContent = '[mermaid render unavailable]';
                    }
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

function startIndexingDashboard() {
    if (els.indexingDashboard) els.indexingDashboard.classList.remove('hidden');
    if (els.indexingProgressBar) els.indexingProgressBar.style.width = '5%';
    if (els.progressTierTitle) els.progressTierTitle.textContent = 'Initializing 3-Tier Pipeline...';
    if (els.progressHeartbeatBadge) els.progressHeartbeatBadge.textContent = 'Active (just now)';
    if (els.progressElapsedTimer) els.progressElapsedTimer.textContent = '00:00';

    [1, 2, 3].forEach(step => {
        const card = els[`stepperTier${step}`];
        const status = els[`stepperStatus${step}`];
        if (card) {
            card.dataset.status = 'pending';
            card.classList.remove('active', 'success', 'error');
        }
        if (status) status.textContent = 'Queued';
    });

    state.indexingStartTime = Date.now();
    if (state.indexingTimer) clearInterval(state.indexingTimer);
    state.indexingTimer = setInterval(() => {
        if (!state.indexingStartTime || !els.progressElapsedTimer) return;
        const elapsedSec = Math.floor((Date.now() - state.indexingStartTime) / 1000);
        const mins = String(Math.floor(elapsedSec / 60)).padStart(2, '0');
        const secs = String(elapsedSec % 60).padStart(2, '0');
        els.progressElapsedTimer.textContent = `${mins}:${secs}`;
    }, 1000);
}

function updateIndexingStepStart(data) {
    const step = data.step || 1;
    const titles = {
        1: 'Tier 1: Graphify (Architecture & AST)',
        2: 'Tier 2: GitNexus (Tree-sitter Execution Flow)',
        3: 'Tier 3: CodeGraph (Symbol Dependencies & Impact)'
    };
    if (els.progressTierTitle) {
        els.progressTierTitle.textContent = titles[step] || `Tier ${step}: ${data.engine || 'Engine'}`;
    }
    if (els.progressHeartbeatBadge) {
        els.progressHeartbeatBadge.textContent = 'Running...';
    }

    // Mark previous steps as success
    for (let i = 1; i < step; i++) {
        const prevCard = els[`stepperTier${i}`];
        const prevStatus = els[`stepperStatus${i}`];
        if (prevCard) {
            prevCard.dataset.status = 'success';
            prevCard.classList.remove('active');
            prevCard.classList.add('success');
        }
        if (prevStatus) prevStatus.textContent = 'Complete';
    }

    // Mark current step as active
    const curCard = els[`stepperTier${step}`];
    const curStatus = els[`stepperStatus${step}`];
    if (curCard) {
        curCard.dataset.status = 'active';
        curCard.classList.add('active');
        curCard.classList.remove('success', 'error');
    }
    if (curStatus) curStatus.textContent = 'Active';

    // Progress bar fill: 15% -> 45% -> 75%
    const pct = step === 1 ? 15 : (step === 2 ? 45 : 75);
    if (els.indexingProgressBar) els.indexingProgressBar.style.width = `${pct}%`;
}

function updateIndexingHeartbeat(data) {
    if (!els.progressHeartbeatBadge) return;
    const elapsed = data.elapsed_seconds ? ` (${data.elapsed_seconds}s)` : '';
    els.progressHeartbeatBadge.textContent = `Active${elapsed}`;
}

function updateIndexingLog(data) {
    if (els.progressHeartbeatBadge && els.progressHeartbeatBadge.textContent !== 'Active (just now)') {
        els.progressHeartbeatBadge.textContent = 'Active (just now)';
    }
}

function updateIndexingStepFinish(data) {
    const step = data.step || 1;
    const ok = data.success !== false;
    const card = els[`stepperTier${step}`];
    const status = els[`stepperStatus${step}`];
    if (card) {
        card.dataset.status = ok ? 'success' : 'error';
        card.classList.remove('active');
        card.classList.add(ok ? 'success' : 'error');
    }
    if (status) status.textContent = ok ? 'Complete' : 'Failed';

    const pct = step === 1 ? 33 : (step === 2 ? 66 : 95);
    if (els.indexingProgressBar) els.indexingProgressBar.style.width = `${pct}%`;
}

function updateIndexingStepError(data) {
    const step = data.step || 1;
    const card = els[`stepperTier${step}`];
    const status = els[`stepperStatus${step}`];
    if (card) {
        card.dataset.status = 'error';
        card.classList.remove('active');
        card.classList.add('error');
    }
    if (status) status.textContent = 'Failed';
}

async function runIndexing() {
    if (state.inFlight) return;
    document.getElementById('unindexed-overlay')?.remove();
    persistUiTokenFromInput();
    const force = els.forceIndex ? els.forceIndex.checked : false;
    const multi = els.multimodalIndex ? els.multimodalIndex.checked : false;

    setBusy(true);
    openDrawer();
    switchDrawerTab('terminal');
    startIndexingDashboard();
    els.terminalOutput.textContent = `[CKC Engine] Initiating 3-Tier Indexing for ${state.currentProject}...\n`;
    showToast('Started 3-Tier Indexing pipeline', 'info');

    if (els.cancelIndexBtn) els.cancelIndexBtn.classList.remove('hidden');
    if (els.runIndexBtn) els.runIndexBtn.classList.add('hidden');

    const controller = new AbortController();
    state.indexingAbort = controller;
    state._indexingDone = false;

    try {
        const res = await fetch('/api/index/stream', {
            method: 'POST',
            credentials: 'omit',
            headers: authHeaders({ Accept: 'text/event-stream' }),
            body: JSON.stringify({
                project_path: state.currentProject,
                multimodal: multi,
                force,
            }),
            signal: controller.signal,
        });
        if (!res.ok) {
            let errMessage = `HTTP ${res.status} ${res.statusText}`;
            try {
                const errData = await res.json();
                if (errData && errData.detail) errMessage = formatApiDetail(errData.detail);
            } catch (_) { /* ignore */ }
            throw new Error(errMessage);
        }
        await consumeSseStream(res.body, handleIndexingEvent);
        if (!state._indexingDone) {
            finishIndexing(false, 'Indexing stream ended unexpectedly.');
        }
    } catch (e) {
        if (e && e.name === 'AbortError') {
            if (!state._indexingDone) {
                finishIndexing(false, 'Indexing cancelled by user.');
            }
            return;
        }
        console.error('SSE Error:', e);
        if (!state._indexingDone) {
            finishIndexing(false, e.message || 'Indexing connection interrupted or failed.');
        }
    }
}

async function consumeSseStream(body, onEvent) {
    if (!body) return;
    const reader = body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n');
        buffer = parts.pop() || '';
        for (const rawLine of parts) {
            const line = rawLine.replace(/\r$/, '');
            if (!line.startsWith('data:')) continue;
            const payload = line.slice(5).trimStart();
            if (!payload || payload === '[DONE]') continue;
            try {
                onEvent(JSON.parse(payload));
            } catch (_) {
                els.terminalOutput.textContent += `${payload}\n`;
                els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
            }
            if (state._indexingDone) {
                try { await reader.cancel(); } catch (_) { /* ignore */ }
                return;
            }
        }
    }
}

function handleIndexingEvent(data) {
    const text = data.message || data.log || data.line || JSON.stringify(data);
    els.terminalOutput.textContent += `${text}\n`;
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;

    const eventType = data.event || data.type;

    if (eventType === 'start') {
        startIndexingDashboard();
    } else if (eventType === 'step_start') {
        updateIndexingStepStart(data);
    } else if (eventType === 'heartbeat') {
        updateIndexingHeartbeat(data);
    } else if (eventType === 'log') {
        updateIndexingLog(data);
    } else if (eventType === 'step_finish') {
        updateIndexingStepFinish(data);
    } else if (eventType === 'step_error') {
        updateIndexingStepError(data);
    } else if (eventType === 'complete') {
        const ok = data.overall_success !== false;
        finishIndexing(ok, ok ? 'Indexing completed successfully.' : 'Indexing finished with errors.');
    } else if (eventType === 'cancelled') {
        finishIndexing(false, data.message || 'Indexing cancelled by user.');
    } else if (eventType === 'error') {
        finishIndexing(false, data.message || 'Indexing error occurred.');
    }
}

function finishIndexing(success, msg) {
    if (state._indexingDone) return;
    state._indexingDone = true;
    if (state.indexingAbort && typeof state.indexingAbort.abort === 'function') {
        state.indexingAbort.abort();
    }
    state.indexingAbort = null;
    if (state.indexingTimer) {
        clearInterval(state.indexingTimer);
        state.indexingTimer = null;
    }

    if (els.cancelIndexBtn) els.cancelIndexBtn.classList.add('hidden');
    if (els.runIndexBtn) els.runIndexBtn.classList.remove('hidden');
    setBusy(false);

    if (success) {
        if (els.indexingProgressBar) els.indexingProgressBar.style.width = '100%';
        if (els.progressTierTitle) els.progressTierTitle.textContent = 'All 3 Tiers Indexed Successfully';
        if (els.progressHeartbeatBadge) els.progressHeartbeatBadge.textContent = 'Complete';
        [1, 2, 3].forEach(step => {
            const card = els[`stepperTier${step}`];
            const status = els[`stepperStatus${step}`];
            if (card && card.dataset.status !== 'error') {
                card.dataset.status = 'success';
                card.classList.remove('active');
                card.classList.add('success');
            }
            if (status && status.textContent !== 'Failed') status.textContent = 'Complete';
        });
    } else {
        if (els.progressTierTitle) els.progressTierTitle.textContent = 'Indexing Stopped';
        if (els.progressHeartbeatBadge) els.progressHeartbeatBadge.textContent = 'Stopped';
    }

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
    if (!state.currentProject || state._indexingDone) return;
    const abort = () => {
        if (state.indexingAbort && typeof state.indexingAbort.abort === 'function') {
            state.indexingAbort.abort();
        }
    };
    try {
        await apiFetch('/api/index/cancel', {
            method: 'POST',
            body: JSON.stringify({ project_path: state.currentProject })
        });
        abort();
        // finishIndexing no-ops if a complete/cancelled SSE already finalized the UI.
        if (!state._indexingDone) {
            finishIndexing(false, 'Indexing cancelled by user.');
        }
    } catch (e) {
        console.error('Failed to cancel indexing:', e);
        // Still tear down the client stream so the UI cannot stick in "indexing".
        abort();
        if (!state._indexingDone) {
            finishIndexing(false, e.message || 'Cancel request failed; stopped local stream.');
        }
    }
}

// ==========================================================================
// Bottom Drawer Management
// ==========================================================================

function openDrawer() {
    state.drawerOpen = true;
    els.drawer.classList.add('open');
    if (els.drawerToggle) els.drawerToggle.setAttribute('aria-expanded', 'true');
}

function closeDrawer() {
    state.drawerOpen = false;
    els.drawer.classList.remove('open');
    if (els.drawerToggle) els.drawerToggle.setAttribute('aria-expanded', 'false');
}

function toggleDrawer() {
    state.drawerOpen = !state.drawerOpen;
    els.drawer.classList.toggle('open', state.drawerOpen);
    if (els.drawerToggle) {
        els.drawerToggle.setAttribute('aria-expanded', state.drawerOpen ? 'true' : 'false');
    }
}

function switchDrawerTab(tab) {
    state.drawerTab = tab;
    els.tabBtns.forEach(btn => {
        const active = btn.dataset.tab === tab;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });

    document.querySelectorAll('.tab-pane').forEach(pane => {
        pane.classList.remove('active');
    });

    const activePane = document.getElementById(`pane-${tab}`);
    if (activePane) activePane.classList.add('active');
}

// ==========================================================================
// Folder Browser
// ==========================================================================

async function openFolderBrowser() {
    if (!els.folderBrowserDialog) return;
    closeAllPopovers({ restoreFocus: false });
    const startPath = state.currentProject || localStorage.getItem('ckc_last_browse_dir') || localStorage.getItem('ckc_project_path') || '';
    if (!els.folderBrowserDialog.open) {
        els.folderBrowserDialog.showModal();
    }
    await navigateBrowserTo(startPath || null);
}

async function navigateBrowserTo(path) {
    if (!els.browserList) return;
    els.browserList.innerHTML = `
        <div class="browser-loading">
            <svg class="btn-spinner" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10" stroke-dasharray="32" stroke-dashoffset="12"></circle>
            </svg>
            <span>Loading directories...</span>
        </div>
    `;
    try {
        const res = await apiFetch('/api/browse', {
            method: 'POST',
            body: JSON.stringify({ path: path })
        });
        renderBrowserContents(res);
    } catch (e) {
        console.error('Browse failed:', e);
        els.browserList.innerHTML = `
            <div class="browser-error">
                <div class="browser-error-title">Could not load directory</div>
                <div class="browser-error-msg">${escapeHtml(e.message)}</div>
                <div class="browser-error-actions">
                    <button type="button" class="btn btn-secondary btn-sm" id="browser-error-home-btn">Go to Home Directory</button>
                    <button type="button" class="btn btn-secondary btn-sm" id="browser-error-root-btn">Go to Root (/)</button>
                </div>
            </div>
        `;
        document.getElementById('browser-error-home-btn')?.addEventListener('click', () => navigateBrowserTo(null));
        document.getElementById('browser-error-root-btn')?.addEventListener('click', () => navigateBrowserTo('/'));
        showToast(`Browse failed: ${e.message}`, 'error');
    }
}

function renderBrowserContents(data) {
    if (data && data.current) {
        localStorage.setItem('ckc_last_browse_dir', data.current);
    }
    // Breadcrumbs
    if (els.browserBreadcrumbs) {
        els.browserBreadcrumbs.innerHTML = '';
        const parts = data.current.split('/').filter(Boolean);
        let accumulated = '';
        
        // Root
        const rootBtn = document.createElement('button');
        rootBtn.type = 'button';
        rootBtn.className = 'breadcrumb-item';
        rootBtn.textContent = '/';
        rootBtn.addEventListener('click', () => navigateBrowserTo('/'));
        els.browserBreadcrumbs.appendChild(rootBtn);
        
        parts.forEach((part, idx) => {
            accumulated += '/' + part;
            const sep = document.createElement('span');
            sep.className = 'breadcrumb-sep';
            sep.textContent = '›';
            els.browserBreadcrumbs.appendChild(sep);
            
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'breadcrumb-item';
            if (idx === parts.length - 1) btn.classList.add('active');
            btn.textContent = part;
            const targetPath = accumulated;
            btn.addEventListener('click', () => navigateBrowserTo(targetPath));
            els.browserBreadcrumbs.appendChild(btn);
        });
    }
    
    // Directory listing
    if (els.browserList) {
        els.browserList.innerHTML = '';
        
        // Parent directory entry
        if (data.parent) {
            const parentItem = document.createElement('button');
            parentItem.type = 'button';
            parentItem.className = 'browser-item browser-item-parent';
            parentItem.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
                <span>..</span>
            `;
            parentItem.addEventListener('click', () => navigateBrowserTo(data.parent));
            els.browserList.appendChild(parentItem);
        }
        
        if (!data.entries || data.entries.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'browser-empty';
            empty.textContent = 'No subdirectories';
            els.browserList.appendChild(empty);
        } else {
            data.entries.forEach(entry => {
                const item = document.createElement('button');
                item.type = 'button';
                item.className = 'browser-item';
                const badgeHtml = entry.is_indexed ? '<span class="browser-item-badge">Indexed</span>' : '';
                item.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <span>${escapeHtml(entry.name)}</span>
                    ${badgeHtml}
                `;
                const targetPath = data.current + (data.current.endsWith('/') ? '' : '/') + entry.name;
                item.addEventListener('click', () => navigateBrowserTo(targetPath));
                els.browserList.appendChild(item);
            });
        }
    }
    
    // Update selected path display
    if (els.browserSelectedPath) {
        els.browserSelectedPath.textContent = data.current;
        els.browserSelectedPath.title = data.current;
    }
}

function closeFolderBrowser() {
    if (els.folderBrowserDialog && els.folderBrowserDialog.open) {
        els.folderBrowserDialog.close();
    }
}

function confirmFolderSelection() {
    const selected = els.browserSelectedPath ? els.browserSelectedPath.textContent : '';
    if (!selected || selected === '—') return;
    
    state.currentProject = selected;
    sessionStorage.setItem('ckc_project_path', state.currentProject);
    localStorage.setItem('ckc_project_path', state.currentProject);
    localStorage.setItem('ckc_last_browse_dir', state.currentProject);
    if (els.projectInput) els.projectInput.value = selected;
    if (els.projectPathText) {
        els.projectPathText.textContent = getProjectShortName(selected);
        els.projectPathText.title = selected;
    }
    updateProjectLabel();
    closeFolderBrowser();
    closeAllPopovers({ restoreFocus: false });
    loadProject();
    if (!localStorage.getItem('ckc_has_seen_tour')) {
        setTimeout(() => startOnboardingTour(false), 1200);
    }
}

// ==========================================================================
// Recent Projects Management
// ==========================================================================

function getRecentProjects() {
    try {
        const raw = localStorage.getItem('ckc_recent_projects');
        return raw ? JSON.parse(raw) : [];
    } catch (_) {
        return [];
    }
}

function addRecentProject(projectPath, meta = {}) {
    if (!projectPath) return;
    let list = getRecentProjects().filter(p => p.path !== projectPath);
    const shortName = getProjectShortName(projectPath);
    list.unshift({
        path: projectPath,
        name: shortName,
        lastOpened: Date.now(),
        indexed: meta.indexed !== undefined ? !!meta.indexed : false,
        nodeCount: meta.nodeCount || 0,
        edgeCount: meta.edgeCount || 0
    });
    list = list.slice(0, 8);
    try {
        localStorage.setItem('ckc_recent_projects', JSON.stringify(list));
    } catch (_) {}
    renderRecentProjects();
}

function clearRecentProjects() {
    localStorage.removeItem('ckc_recent_projects');
    renderRecentProjects();
}

function renderRecentProjects() {
    if (!els.recentProjectsList) return;
    const list = getRecentProjects();
    els.recentProjectsList.innerHTML = '';
    if (list.length === 0) {
        els.recentProjectsList.innerHTML = '<span class="empty-recent-text">No recent repositories</span>';
        return;
    }

    list.forEach(item => {
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'recent-project-item';
        if (item.path === state.currentProject) {
            row.classList.add('active');
        }

        const pillClass = item.indexed ? 'recent-project-pill indexed' : 'recent-project-pill unindexed';
        const pillText = item.indexed
            ? (item.nodeCount ? `${item.nodeCount.toLocaleString()} symbols` : 'Indexed')
            : 'Unindexed';

        row.innerHTML = `
            <div class="recent-project-info">
                <span class="recent-project-name">${escapeHtml(item.name)}</span>
                <span class="recent-project-path">${escapeHtml(item.path)}</span>
            </div>
            <span class="${pillClass}">${escapeHtml(pillText)}</span>
        `;
        row.addEventListener('click', () => {
            switchToProject(item.path);
        });
        els.recentProjectsList.appendChild(row);
    });
}

async function switchToProject(projectPath) {
    if (!projectPath || state.inFlight) return;
    closeAllPopovers({ restoreFocus: false });
    state.currentProject = projectPath;
    sessionStorage.setItem('ckc_project_path', state.currentProject);
    localStorage.setItem('ckc_project_path', state.currentProject);
    localStorage.setItem('ckc_last_browse_dir', state.currentProject);
    if (els.projectInput) els.projectInput.value = state.currentProject;
    if (els.projectPathText) {
        els.projectPathText.textContent = getProjectShortName(state.currentProject);
        els.projectPathText.title = state.currentProject;
    }
    updateProjectLabel();
    renderRecentProjects();
    await loadProject();
}

// ==========================================================================
// Indexing Option Dependencies
// ==========================================================================

function updateIndexingDependencies() {
    const llmEnabled = els.useLlm ? els.useLlm.checked : false;
    const multiInput = els.multimodalIndex;
    const depWarning = document.getElementById('llm-dep-warning');
    const multiLabel = document.getElementById('multimodal-label');

    if (multiInput) {
        if (!llmEnabled) {
            multiInput.checked = false;
            multiInput.disabled = true;
            if (multiLabel) multiLabel.classList.add('disabled');
            if (depWarning) depWarning.classList.remove('hidden');
        } else {
            multiInput.disabled = false;
            if (multiLabel) multiLabel.classList.remove('disabled');
            if (depWarning) depWarning.classList.add('hidden');
        }
    }
}

// ==========================================================================
// BYOK (Bring Your Own Key) Provider Management
// ==========================================================================

async function checkLlmStatus() {
    try {
        const res = await apiFetch('/api/llm/status');
        state.byok = {
            provider: res.provider || 'lm-studio',
            baseUrl: res.base_url || 'http://127.0.0.1:1234/v1',
            model: res.model || null,
            apiKey: '',
            connected: !!res.connected,
            configured: !!res.configured,
            models: res.available_models || [],
            error: res.error || null
        };
        updateLlmBadges();
        return res;
    } catch (e) {
        console.warn('Failed to fetch LLM status:', e);
        state.byok.connected = false;
        updateLlmBadges();
        return null;
    }
}

function updateLlmBadges() {
    if (els.headerAiDot && els.headerAiLabel) {
        if (state.byok.connected) {
            els.headerAiDot.className = 'ai-status-dot active';
            const provName = state.byok.provider === 'lm-studio' ? 'LM Studio' : (state.byok.provider === 'ollama' ? 'Ollama' : (state.byok.provider === 'openai' ? 'OpenAI' : 'Custom LLM'));
            els.headerAiLabel.textContent = provName;
            els.headerAiBtn.title = `AI Connected: ${state.byok.model || provName} (${state.byok.baseUrl})`;
        } else {
            els.headerAiDot.className = state.byok.configured ? 'ai-status-dot offline' : 'ai-status-dot';
            els.headerAiLabel.textContent = state.byok.provider === 'lm-studio' ? 'LM Studio' : (state.byok.configured ? 'AI Offline' : 'AI Setup');
            els.headerAiBtn.title = state.byok.error || 'AI Provider Disconnected (Click to configure BYOK)';
        }
    }

    if (els.llmChip) {
        if (state.byok.connected) {
            els.llmChip.textContent = `LLM: ${state.byok.model || state.byok.provider}`;
            els.llmChip.className = 'badge-chip badge-chip-interactive badge-ready';
        } else {
            els.llmChip.textContent = state.byok.configured ? 'LLM: Error' : 'LLM: Off';
            els.llmChip.className = 'badge-chip badge-chip-interactive';
        }
    }
}

function openByokDialog() {
    if (!els.byokDialog) return;
    closeAllPopovers({ restoreFocus: false });
    if (els.byokBaseUrl) els.byokBaseUrl.value = state.byok.baseUrl;
    if (els.byokApiKey) els.byokApiKey.value = state.byok.apiKey || '';
    selectProviderPreset(state.byok.provider || 'lm-studio', false);
    if (!els.byokDialog.open) {
        els.byokDialog.showModal();
    }
    probeByokProvider();
}

function closeByokDialog() {
    if (els.byokDialog && els.byokDialog.open) {
        els.byokDialog.close();
    }
}

function selectProviderPreset(provider, updateUrl = true) {
    document.querySelectorAll('.provider-pill').forEach(pill => {
        pill.classList.toggle('active', pill.dataset.provider === provider);
    });
    const guideCard = document.getElementById('lmstudio-guide-card');

    if (updateUrl && els.byokBaseUrl) {
        if (provider === 'lm-studio') {
            els.byokBaseUrl.value = 'http://127.0.0.1:1234/v1';
        } else if (provider === 'ollama') {
            els.byokBaseUrl.value = 'http://127.0.0.1:11434/v1';
        } else if (provider === 'openai') {
            els.byokBaseUrl.value = 'https://api.openai.com/v1';
        }
    }

    if (provider === 'lm-studio') {
        if (guideCard && !state.byok.connected) guideCard.classList.remove('hidden');
    } else {
        if (guideCard) guideCard.classList.add('hidden');
    }
}

async function probeByokProvider() {
    const statusCard = document.getElementById('byok-status-card');
    const statusIcon = document.getElementById('byok-status-icon');
    const headline = document.getElementById('byok-status-headline');
    const sub = document.getElementById('byok-status-sub');
    const retryBtn = els.byokRetryBtn;
    const guideCard = document.getElementById('lmstudio-guide-card');

    if (statusIcon) statusIcon.innerHTML = '<span class="status-indicator status-probing"></span>';
    if (headline) headline.textContent = 'Detecting Provider...';
    if (sub) sub.textContent = 'Checking connectivity and listing available models...';
    if (retryBtn) {
        const spinner = retryBtn.querySelector('.btn-spinner');
        if (spinner) spinner.classList.remove('hidden');
    }

    const res = await checkLlmStatus();

    if (retryBtn) {
        const spinner = retryBtn.querySelector('.btn-spinner');
        if (spinner) spinner.classList.add('hidden');
    }

    if (res && res.connected) {
        if (statusCard) {
            statusCard.className = 'byok-status-card connected';
        }
        if (statusIcon) {
            statusIcon.innerHTML = '<span class="status-indicator status-connected"></span>';
        }
        if (headline) {
            headline.textContent = `Connected (${res.provider.toUpperCase()})`;
        }
        if (sub) {
            sub.textContent = res.model ? `Active Model: ${res.model}` : `${res.available_models.length} model(s) available`;
        }
        if (guideCard) guideCard.classList.add('hidden');

        // Populate models dropdown
        if (els.byokModelSelect) {
            els.byokModelSelect.innerHTML = '';
            if (res.available_models && res.available_models.length > 0) {
                res.available_models.forEach(m => {
                    const opt = document.createElement('option');
                    opt.value = m;
                    opt.textContent = m;
                    if (m === res.model) opt.selected = true;
                    els.byokModelSelect.appendChild(opt);
                });
            } else {
                const opt = document.createElement('option');
                opt.value = res.model || 'local-model';
                opt.textContent = res.model || 'local-model';
                opt.selected = true;
                els.byokModelSelect.appendChild(opt);
            }
            const customOpt = document.createElement('option');
            customOpt.value = '__custom__';
            customOpt.textContent = 'Custom model name...';
            els.byokModelSelect.appendChild(customOpt);
        }
    } else {
        if (statusCard) {
            statusCard.className = 'byok-status-card disconnected';
        }
        if (statusIcon) {
            statusIcon.innerHTML = '<span class="status-indicator status-disconnected"></span>';
        }
        if (headline) {
            headline.textContent = 'Server Not Reachable';
        }
        if (sub) {
            sub.textContent = (res && res.error) || 'Could not connect to provider endpoint.';
        }
        const activeProvider = document.querySelector('.provider-pill.active')?.dataset.provider;
        if (guideCard && activeProvider === 'lm-studio') {
            guideCard.classList.remove('hidden');
        }
        if (els.byokModelSelect) {
            els.byokModelSelect.innerHTML = '<option value="">(No models detected - server offline)</option><option value="__custom__">Specify custom model...</option>';
        }
    }
}

async function saveByokConfig() {
    const activePill = document.querySelector('.provider-pill.active');
    const provider = activePill ? activePill.dataset.provider : 'lm-studio';
    const baseUrl = (els.byokBaseUrl ? els.byokBaseUrl.value : '').trim();
    const apiKey = (els.byokApiKey ? els.byokApiKey.value : '').trim();

    let model = '';
    if (els.byokModelSelect && els.byokModelSelect.value === '__custom__') {
        model = (els.byokModelCustom ? els.byokModelCustom.value : '').trim();
    } else if (els.byokModelSelect) {
        model = els.byokModelSelect.value;
    }

    if (!baseUrl) {
        showToast('Please specify a base URL', 'error');
        return;
    }

    try {
        const res = await apiFetch('/api/llm/config', {
            method: 'POST',
            body: JSON.stringify({
                provider: provider,
                base_url: baseUrl,
                api_key: apiKey || null,
                model: model || null
            })
        });

        await checkLlmStatus();
        if (els.useLlm && !els.useLlm.checked) {
            els.useLlm.checked = true;
            persistUseLlmFromInput();
            updateIndexingDependencies();
        }

        if (res.connected) {
            showToast(`AI Provider connected: ${res.model || provider}`, 'success');
        } else {
            showToast(`Provider saved, but connection failed: ${res.error || 'Offline'}`, 'info');
        }
        closeByokDialog();
    } catch (e) {
        showToast(`Configuration error: ${e.message}`, 'error');
    }
}

async function skipByok() {
    try {
        await apiFetch('/api/llm/disable', { method: 'POST' });
        if (els.useLlm) {
            els.useLlm.checked = false;
            persistUseLlmFromInput();
            updateIndexingDependencies();
        }
        await checkLlmStatus();
        closeByokDialog();
        showToast('Offline Mode: Pure 3-tier local AST code intelligence active.', 'info');
    } catch (e) {
        console.error('Failed to disable LLM:', e);
        closeByokDialog();
    }
}

// ==========================================================================
// Driver.js Onboarding Tour
// ==========================================================================

function initOnboardingTour() {
    if (localStorage.getItem('ckc_has_seen_tour')) return;
    if (els.folderBrowserDialog && els.folderBrowserDialog.open) return;
    // Delay to let the UI settle
    setTimeout(() => {
        if (els.folderBrowserDialog && els.folderBrowserDialog.open) return;
        startOnboardingTour(false);
    }, 800);
}

function startOnboardingTour(isRestart) {
    if (!window.driver || !window.driver.js) return;
    const createDriver = window.driver.js.driver;
    
    const tourDriver = createDriver({
        showProgress: true,
        animate: true,
        allowClose: true,
        stagePadding: 8,
        stageRadius: 8,
        popoverClass: 'ckc-tour',
        nextBtnText: 'Next →',
        prevBtnText: '← Back',
        doneBtnText: 'Get Started!',
        showButtons: ['next', 'previous', 'close'],
        steps: [
            {
                popover: {
                    title: 'Welcome to CKC! 🚀',
                    description: 'Code Knowledge Chain visualizes your codebase as an interactive 3D knowledge graph. Let\'s take a quick tour of the key features.'
                }
            },
            {
                element: '#project-pill-btn',
                popover: {
                    title: 'Select a Repository',
                    description: 'Click here to open your local repository. Use the folder browser to navigate to your project directory.',
                    side: 'bottom',
                    align: 'start'
                }
            },
            {
                element: '#header-index-btn',
                popover: {
                    title: 'Index Your Codebase',
                    description: 'Build the 3-tier knowledge graph by indexing your code with Graphify, GitNexus, and CodeGraph engines.',
                    side: 'bottom',
                    align: 'end'
                }
            },
            {
                element: '#command-bar',
                popover: {
                    title: 'Search & Analyze',
                    description: 'Search symbols, ask architecture questions, analyze blast radius, or trace execution paths. Try "A → B" to trace a call path.',
                    side: 'bottom',
                    align: 'center'
                }
            },
            {
                element: '#layers-toggle-btn',
                popover: {
                    title: 'Filter & Explore',
                    description: 'Filter graph nodes by type (code, docs, schemas, tests) and explore module clusters to understand your architecture.',
                    side: 'bottom',
                    align: 'end'
                }
            }
        ],
        onDestroyed: () => {
            localStorage.setItem('ckc_has_seen_tour', '1');
        }
    });
    
    tourDriver.drive();
}

function addOperationHistory(type, param) {
    if (!els.opsHistory) return;
    const emptyText = els.opsHistory.querySelector('.empty-ops-text');
    if (emptyText) emptyText.remove();

    const chip = document.createElement('button');
    chip.type = 'button';
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
        const content = textNode.textContent;
        if (!content) return;

        const matches = [];
        for (const label of sortedLabels) {
            const regex = new RegExp(`\\b(${label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b`, 'g');
            let m;
            while ((m = regex.exec(content)) !== null) {
                matches.push({ start: m.index, end: m.index + m[0].length, label: m[1] });
            }
        }
        if (!matches.length) return;

        matches.sort((a, b) => a.start - b.start || b.end - a.end);
        const chosen = [];
        let cursor = 0;
        for (const m of matches) {
            if (m.start < cursor) continue;
            chosen.push(m);
            cursor = m.end;
        }
        if (!chosen.length) return;

        const frag = document.createDocumentFragment();
        let last = 0;
        chosen.forEach((m) => {
            if (m.start > last) {
                frag.appendChild(document.createTextNode(content.slice(last, m.start)));
            }
            const a = document.createElement('a');
            a.href = '#';
            a.className = 'symbol-link';
            a.textContent = m.label;
            a.addEventListener('click', (e) => {
                e.preventDefault();
                selectNodeByLabel(m.label);
            });
            frag.appendChild(a);
            last = m.end;
        });
        if (last < content.length) {
            frag.appendChild(document.createTextNode(content.slice(last)));
        }
        textNode.parentNode.replaceChild(frag, textNode);
    });
}

// Start application
document.addEventListener('DOMContentLoaded', init);
