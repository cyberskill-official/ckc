// CKC Graph-First Explorer App

const state = {
    currentProject: localStorage.getItem('ckc_project_path') || '',
    cy: null,
    selectedNode: null,
    traceSource: null,
    graphData: null,
    communities: [],
    filters: { code: true, doc: true, schema: true, test: true },
    indexingSource: null,
    operationHistory: [],
    drawerOpen: false,
    drawerTab: 'terminal',
    lastResults: '',
    palette: [
        '#ff7b72', '#79c0ff', '#d2a8ff', '#a5d6ff', '#f0883e', 
        '#3fb950', '#8957e5', '#d29922', '#ff9bce', '#56d364',
        '#e3b341', '#f85149'
    ]
};

// UI Elements
const els = {
    projectInput: document.getElementById('project-path'),
    loadBtn: document.getElementById('load-btn'),
    readyBadge: document.getElementById('ready-badge'),
    llmChip: document.getElementById('llm-chip'),
    
    // Sidebar
    filterCode: document.getElementById('filter-code'),
    filterDoc: document.getElementById('filter-doc'),
    filterSchema: document.getElementById('filter-schema'),
    filterTest: document.getElementById('filter-test'),
    communityList: document.getElementById('community-list'),
    runIndexBtn: document.getElementById('run-index-btn'),
    forceIndex: document.getElementById('force-index'),
    multimodalIndex: document.getElementById('multimodal-index'),
    opsHistory: document.getElementById('ops-history'),
    
    // Graph Area
    commandBar: document.getElementById('command-bar'),
    fitBtn: document.getElementById('fit-btn'),
    clearOverlaysBtn: document.getElementById('clear-overlays-btn'),
    
    // Right Panel
    contextPanel: document.getElementById('context-panel'),
    closePanelBtn: document.getElementById('close-panel-btn'),
    nodeDetails: document.getElementById('node-details'),
    
    // Drawer
    drawer: document.getElementById('drawer'),
    drawerToggle: document.getElementById('drawer-toggle'),
    tabBtns: document.querySelectorAll('.tab-btn'),
    terminalOutput: document.getElementById('terminal-output'),
    resultsOutput: document.getElementById('results-output')
};

// Initialization
function init() {
    els.projectInput.value = state.currentProject;
    
    initCytoscape();
    setupEventListeners();
    
    if (state.currentProject) {
        loadProject();
    }
}

function initCytoscape() {
    state.cy = cytoscape({
        container: document.getElementById('cy'),
        style: [
            {
                selector: 'node',
                style: {
                    'label': 'data(label)',
                    'font-size': '10px',
                    'color': '#c9d1d9',
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-margin-y': 4,
                    'min-zoomed-font-size': 8
                }
            },
            {
                selector: 'node[category="code"]',
                style: { 'shape': 'ellipse', 'background-color': '#8b949e' }
            },
            {
                selector: 'node[category="doc"]',
                style: { 'shape': 'diamond', 'background-color': '#d2a8ff' }
            },
            {
                selector: 'node[category="schema"]',
                style: { 'shape': 'hexagon', 'background-color': '#d29922' }
            },
            {
                selector: 'node[category="test"]',
                style: { 'shape': 'triangle', 'background-color': '#79c0ff' }
            },
            {
                selector: 'edge',
                style: {
                    'width': 1,
                    'line-color': '#30363d',
                    'curve-style': 'bezier',
                    'target-arrow-shape': 'triangle',
                    'target-arrow-color': '#30363d',
                    'arrow-scale': 0.8
                }
            },
            {
                selector: ':selected',
                style: {
                    'border-width': 3,
                    'border-color': '#58a6ff'
                }
            },
            {
                selector: '.dimmed',
                style: { 'opacity': 0.3 }
            },
            {
                selector: '.trace-source',
                style: {
                    'border-width': 3,
                    'border-color': '#f0883e'
                }
            },
            {
                selector: '.impact-target',
                style: { 'background-color': '#f85149', 'border-color': '#f85149', 'border-width': 2 }
            },
            {
                selector: '.impact-node',
                style: { 'background-color': '#f0883e' }
            },
            {
                selector: '.trace-edge',
                style: {
                    'line-color': '#58a6ff',
                    'target-arrow-color': '#58a6ff',
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
            handleShiftClick(node);
        } else {
            selectNode(node);
        }
    });

    state.cy.on('tap', function(evt){
        if (evt.target === state.cy) {
            clearSelection();
        }
    });
}

function setupEventListeners() {
    els.loadBtn.addEventListener('click', () => {
        state.currentProject = els.projectInput.value;
        localStorage.setItem('ckc_project_path', state.currentProject);
        loadProject();
    });

    els.projectInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') els.loadBtn.click();
    });

    els.fitBtn.addEventListener('click', () => state.cy.fit(50));
    
    // Filters
    ['Code', 'Doc', 'Schema', 'Test'].forEach(type => {
        els[`filter${type}`].addEventListener('change', (e) => {
            state.filters[type.toLowerCase()] = e.target.checked;
            applyFilters();
        });
    });

    // Right Panel
    els.closePanelBtn.addEventListener('click', () => {
        els.contextPanel.classList.add('closed');
        clearSelection();
    });

    // Drawer
    document.querySelector('.drawer-controls').addEventListener('click', toggleDrawer);
    els.tabBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            els.tabBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            document.getElementById(`pane-${e.target.dataset.tab}`).classList.add('active');
            state.drawerTab = e.target.dataset.tab;
        });
    });

    // Command Bar
    els.commandBar.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleCommand(e.target.value);
    });

    // Global Hotkeys
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            clearSelection();
            clearOverlays();
            els.contextPanel.classList.add('closed');
        } else if (e.key === '/' && document.activeElement !== els.commandBar && document.activeElement.tagName !== 'INPUT') {
            e.preventDefault();
            els.commandBar.focus();
        } else if (e.key === 'f' && document.activeElement.tagName !== 'INPUT') {
            state.cy.fit(50);
        }
    });

    els.clearOverlaysBtn.addEventListener('click', clearOverlays);
    
    // Indexing
    els.runIndexBtn.addEventListener('click', runIndexing);
}

async function loadProject() {
    if (!state.currentProject) return;
    
    try {
        const [statusRes, graphRes] = await Promise.all([
            fetch(`/api/status?project=${encodeURIComponent(state.currentProject)}`).then(r => r.json()),
            fetch(`/api/graph?project=${encodeURIComponent(state.currentProject)}`).then(r => r.json())
        ]);

        updateStatus(statusRes);
        renderGraph(graphRes);
        
    } catch (e) {
        console.error("Failed to load project:", e);
        els.readyBadge.textContent = 'Error';
        els.readyBadge.className = 'badge error';
    }
}

function updateStatus(res) {
    if (res.status && res.status.all_ready) {
        els.readyBadge.textContent = 'Ready';
        els.readyBadge.className = 'badge ready';
    } else {
        els.readyBadge.textContent = 'Indexing...';
        els.readyBadge.className = 'badge error';
    }

    if (res.llm && res.llm.configured) {
        els.llmChip.textContent = `LLM: ${res.llm.model || 'Configured'}`;
        els.llmChip.className = 'badge ready';
    } else {
        els.llmChip.textContent = 'LLM: Off';
        els.llmChip.className = 'badge error';
    }
}

function getCommunityColor(commId) {
    let hash = 0;
    const str = String(commId);
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return state.palette[Math.abs(hash) % state.palette.length];
}

function renderGraph(res) {
    if (!res.elements) return;
    
    state.graphData = res;
    state.communities = res.meta?.communities || [];

    // Pre-process nodes to set colors and sizes
    (res.elements.nodes || []).forEach(n => {
        const degree = n.data.degree || 1;
        const size = Math.max(20, Math.min(60, 20 + degree * 3));
        n.data.width = size;
        n.data.height = size;
        
        if (n.data.category === 'code' && n.data.community) {
            n.data.color = getCommunityColor(n.data.community);
        }
    });

    state.cy.elements().remove();
    state.cy.add(res.elements);
    
    state.cy.style().selector('node[category="code"]').style({
        'background-color': function(ele) { return ele.data('color') || '#8b949e'; },
        'width': 'data(width)',
        'height': 'data(height)'
    }).update();

    try {
        state.cy.layout({
            name: 'cose-bilkent',
            animate: false,
            randomize: true,
            idealEdgeLength: 80,
            nodeRepulsion: 6500,
            nestingFactor: 0.1,
            gravity: 0.25,
            numIter: 2500,
            tile: true,
            tilingPaddingVertical: 10,
            tilingPaddingHorizontal: 10,
        }).run();
    } catch (e) {
        console.warn('cose-bilkent layout unavailable, falling back to cose:', e);
        state.cy.layout({ name: 'cose', animate: false }).run();
    }

    renderCommunities();
}

function renderCommunities() {
    els.communityList.innerHTML = '';
    state.communities.sort((a,b) => b.size - a.size).slice(0, 15).forEach(c => {
        const li = document.createElement('li');
        const color = getCommunityColor(c.id);
        li.innerHTML = `<div class="comm-color" style="background:${color}"></div> Community ${c.id} (${c.size})`;
        li.addEventListener('click', () => {
            const nodes = state.cy.nodes().filter(n => n.data('community') === c.id);
            if (nodes.length) {
                state.cy.nodes().addClass('dimmed');
                nodes.removeClass('dimmed');
                state.cy.fit(nodes, 50);
            }
        });
        els.communityList.appendChild(li);
    });
}

function applyFilters() {
    state.cy.nodes().forEach(node => {
        const cat = node.data('category') || 'code';
        if (state.filters[cat]) node.style('display', 'element');
        else node.style('display', 'none');
    });
}

function selectNode(node) {
    state.cy.nodes().addClass('dimmed');
    node.removeClass('dimmed');
    node.neighborhood().removeClass('dimmed');
    
    state.selectedNode = node.id();
    showContextPanel(node.data());
}

function clearSelection() {
    state.cy.nodes().removeClass('dimmed');
    state.selectedNode = null;
    els.contextPanel.classList.add('closed');
}

function handleShiftClick(node) {
    if (!state.traceSource) {
        state.traceSource = node.id();
        node.addClass('trace-source');
        els.commandBar.placeholder = `Select target node for trace from ${node.data('label')}...`;
    } else if (state.traceSource !== node.id()) {
        runTrace(state.traceSource, node.id());
        state.cy.getElementById(state.traceSource).removeClass('trace-source');
        state.traceSource = null;
        els.commandBar.placeholder = `Search nodes, ask questions, or analyze symbols... (Press '/')`;
    }
}

function showContextPanel(data) {
    els.contextPanel.classList.remove('closed');
    document.querySelector('.empty-state').classList.add('hidden');
    document.querySelector('.node-info').classList.remove('hidden');
    
    document.getElementById('node-label').textContent = data.label || data.id;
    const catBadge = document.getElementById('node-category');
    catBadge.textContent = data.category || 'unknown';
    catBadge.className = `badge cat-${data.category || 'code'}`;
    document.getElementById('node-source').textContent = (data.source_file || '') + (data.source_location ? `:${data.source_location}` : '');
    document.getElementById('node-community').textContent = data.community ?? 'none';
    document.getElementById('node-degree').textContent = data.degree || 0;
    
    // Build connections list from Cytoscape edges
    const connList = document.getElementById('node-connections');
    connList.innerHTML = '';
    const cyNode = state.cy.getElementById(data.id);
    if (cyNode.length) {
        const grouped = {};
        cyNode.connectedEdges().forEach(edge => {
            const rel = edge.data('relation') || 'related';
            if (!grouped[rel]) grouped[rel] = [];
            const other = edge.source().id() === data.id ? edge.target() : edge.source();
            grouped[rel].push(other.data('label') || other.id());
        });
        for (const [rel, targets] of Object.entries(grouped)) {
            const relDiv = document.createElement('div');
            relDiv.className = 'conn-group';
            relDiv.innerHTML = `<strong>${rel}</strong>: ${targets.slice(0, 8).map(t => 
                `<a class="symbol-link" data-symbol="${t}">${t}</a>`
            ).join(', ')}${targets.length > 8 ? ` +${targets.length - 8} more` : ''}`;
            connList.appendChild(relDiv);
        }
        // Make symbol links clickable
        connList.querySelectorAll('.symbol-link').forEach(link => {
            link.addEventListener('click', () => {
                const label = link.dataset.symbol;
                const target = state.cy.nodes().filter(n => n.data('label') === label);
                if (target.length) selectNode(target[0]);
            });
        });
    }
    
    // Actions — use label for API calls (symbol name, not internal graph ID)
    const symbolName = data.label || data.id;
    document.getElementById('action-impact').onclick = () => runImpact(symbolName);
    document.getElementById('action-trace').onclick = () => {
        state.traceSource = data.id;
        state.cy.getElementById(data.id).addClass('trace-source');
        els.commandBar.placeholder = `Shift-click target node for trace from ${symbolName}...`;
    };
    document.getElementById('action-query').onclick = () => runQuery(`How does ${symbolName} work?`);
}

async function handleCommand(val) {
    if (!val.trim()) return;
    
    // Check if it matches a node label first (fuzzy)
    const searchLower = val.trim().toLowerCase();
    const matchNode = state.cy.nodes().filter(n => 
        (n.data('label') || '').toLowerCase() === searchLower
    );
    
    if (val.includes('->') || val.includes('→')) {
        const parts = val.split(/->|→/);
        if (parts.length === 2) runTrace(parts[0].trim(), parts[1].trim());
    } else if (matchNode.length > 0) {
        selectNode(matchNode[0]);
        state.cy.fit(matchNode[0].neighborhood().union(matchNode[0]), 80);
    } else if (/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(val.trim())) {
        // Single identifier — could be a symbol. Try to find on graph first.
        const fuzzy = state.cy.nodes().filter(n => 
            (n.data('label') || '').toLowerCase().includes(searchLower)
        );
        if (fuzzy.length > 0) {
            selectNode(fuzzy[0]);
            state.cy.fit(fuzzy[0].neighborhood().union(fuzzy[0]), 80);
        } else {
            runImpact(val.trim());
        }
    } else {
        runQuery(val);
    }
    els.commandBar.value = '';
}

function openDrawer(tab) {
    els.drawer.classList.add('open');
    state.drawerOpen = true;
    if (tab) document.querySelector(`.tab-btn[data-tab="${tab}"]`).click();
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
    state.cy.elements().removeClass('impact-target impact-node trace-edge trace-source');
    els.clearOverlaysBtn.classList.add('hidden');
}

function addOpToHistory(type, label) {
    const div = document.createElement('div');
    div.className = 'op-chip';
    div.textContent = `${type}: ${label}`;
    els.opsHistory.prepend(div);
    if (els.opsHistory.children.length > 5) els.opsHistory.lastChild.remove();
}

// --- API Interactions ---

async function runQuery(q) {
    openDrawer('results');
    els.resultsOutput.innerHTML = '<i>Running query...</i>';
    addOpToHistory('query', q.substring(0,20));
    
    try {
        const res = await fetch('/api/query', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ project_path: state.currentProject, query: q, use_llm: true })
        }).then(r => r.json());
        
        els.resultsOutput.innerHTML = marked.parse(res.synthesized_context || JSON.stringify(res, null, 2));
    } catch (e) {
        els.resultsOutput.innerHTML = `<span style="color:var(--color-red)">Error: ${e.message}</span>`;
    }
}

async function runImpact(symbol) {
    clearOverlays();
    openDrawer('results');
    els.resultsOutput.innerHTML = `<i>Running impact analysis for <code>${symbol}</code>...</i>`;
    els.clearOverlaysBtn.classList.remove('hidden');
    addOpToHistory('impact', symbol);
    
    // Highlight matching node on graph
    const nodes = state.cy.nodes().filter(n => 
        (n.data('label') || '').toLowerCase() === symbol.toLowerCase() ||
        (n.data('label') || '').toLowerCase().includes(symbol.toLowerCase())
    );
    if (nodes.length > 0) {
        nodes[0].addClass('impact-target');
        state.cy.fit(nodes[0].neighborhood().union(nodes[0]), 50);
    }
    
    try {
        const res = await fetch('/api/impact', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ project_path: state.currentProject, symbol: symbol, use_llm: true })
        }).then(r => r.json());
        
        const html = marked.parse(res.synthesized_report || JSON.stringify(res, null, 2));
        els.resultsOutput.innerHTML = linkifySymbols(html);
        
        // Highlight impacted nodes on graph (call_hierarchy has {depth, symbol, file, relation})
        if (res.call_hierarchy && res.call_hierarchy.length) {
            res.call_hierarchy.forEach(item => {
                const symName = item.symbol || '';
                const match = state.cy.nodes().filter(n => 
                    (n.data('label') || '').toLowerCase() === symName.toLowerCase()
                );
                if (match.length) match[0].addClass('impact-node');
            });
        }
        
    } catch (e) {
        els.resultsOutput.innerHTML = `<span style="color:#f85149">Error: ${e.message}</span>`;
    }
}

async function runTrace(fromSym, toSym) {
    clearOverlays();
    openDrawer('results');
    els.resultsOutput.innerHTML = `<i>Tracing <code>${fromSym}</code> → <code>${toSym}</code>...</i>`;
    els.clearOverlaysBtn.classList.remove('hidden');
    addOpToHistory('trace', `${fromSym}→${toSym}`);
    
    try {
        const res = await fetch('/api/trace', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ project_path: state.currentProject, from_symbol: fromSym, to_symbol: toSym, use_llm: true })
        }).then(r => r.json());
        
        const html = marked.parse(res.synthesized_flow || JSON.stringify(res, null, 2));
        els.resultsOutput.innerHTML = linkifySymbols(html);
        
        // Highlight trace path on graph (steps have {symbol_name, file_path, ...})
        if (res.path_found && res.steps && res.steps.length > 0) {
            const stepNames = res.steps.map(s => s.symbol_name || '');
            stepNames.forEach(name => {
                const match = state.cy.nodes().filter(n => 
                    (n.data('label') || '').toLowerCase() === name.toLowerCase()
                );
                if (match.length) match[0].addClass('impact-node');
            });
            // Try to highlight edges between consecutive step nodes
            for (let i = 0; i < stepNames.length - 1; i++) {
                state.cy.edges().forEach(edge => {
                    const srcLabel = edge.source().data('label') || '';
                    const tgtLabel = edge.target().data('label') || '';
                    if (srcLabel.toLowerCase() === stepNames[i].toLowerCase() && 
                        tgtLabel.toLowerCase() === stepNames[i+1].toLowerCase()) {
                        edge.addClass('trace-edge');
                    }
                });
            }
        }
    } catch (e) {
        els.resultsOutput.innerHTML = `<span style="color:#f85149">Error: ${e.message}</span>`;
    }
}

function runIndexing() {
    if (!state.currentProject) return alert("Please load a project first.");
    openDrawer('terminal');
    els.terminalOutput.textContent = '';
    
    if (state.indexingSource) state.indexingSource.close();
    
    const url = `/api/index/stream?project=${encodeURIComponent(state.currentProject)}&multimodal=${els.multimodalIndex.checked}&force=${els.forceIndex.checked}`;
    state.indexingSource = new EventSource(url);
    
    // Server sends unnamed SSE events with JSON payloads containing an 'event' field
    state.indexingSource.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.event === 'start') {
                appendTerminal(`[CKC] ${data.message}`, 'success');
            } else if (data.event === 'step_start') {
                appendTerminal(`\n[Step ${data.step}/${data.total_steps}] ${data.label}...`, 'info');
            } else if (data.event === 'log') {
                appendTerminal(data.line, data.engine);
            } else if (data.event === 'step_finish') {
                const icon = data.success ? '✓' : '✗';
                appendTerminal(`[${data.engine}] ${icon} ${data.success ? 'Succeeded' : 'Failed (code ' + data.returncode + ')'}`, data.success ? 'success' : 'error');
            } else if (data.event === 'step_error') {
                appendTerminal(`[${data.engine}] Error: ${data.error}`, 'error');
            } else if (data.event === 'cancelled') {
                appendTerminal(`[CKC] ${data.message}`, 'error');
                state.indexingSource.close();
            } else if (data.event === 'complete') {
                appendTerminal(`\n[CKC] Indexing complete! Readiness: ${data.status?.ready_count}/3 engines.`, 'success');
                state.indexingSource.close();
                loadProject();
            }
        } catch (err) {
            appendTerminal(e.data, '');
        }
    };
    
    state.indexingSource.onerror = () => {
        appendTerminal('\nStream closed or error occurred.', 'error');
        state.indexingSource.close();
    };
}

function appendTerminal(text, type) {
    const line = document.createElement('div');
    line.className = `terminal-line ${type ? 'log-' + type : ''}`;
    line.textContent = text;
    els.terminalOutput.appendChild(line);
    els.terminalOutput.scrollTop = els.terminalOutput.scrollHeight;
}

/** Make symbol names in rendered HTML clickable if they match graph nodes */
function linkifySymbols(html) {
    if (!state.cy || !state.graphData) return html;
    const labels = new Set();
    state.cy.nodes().forEach(n => {
        const l = n.data('label');
        if (l && l.length > 2 && /^[a-zA-Z_]/.test(l)) labels.add(l);
    });
    // Wrap backtick-quoted symbol names that match graph labels
    let result = html;
    labels.forEach(label => {
        const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`<code>(${escaped})</code>`, 'g');
        result = result.replace(regex, `<code><a class="symbol-link" onclick="selectNodeByLabel('${label}')" style="cursor:pointer;color:#58a6ff">$1</a></code>`);
    });
    return result;
}

/** Select a node by its label (called from linkified symbols) */
window.selectNodeByLabel = function(label) {
    const node = state.cy.nodes().filter(n => n.data('label') === label);
    if (node.length) {
        selectNode(node[0]);
        state.cy.fit(node[0].neighborhood().union(node[0]), 80);
    }
};

window.onload = init;
