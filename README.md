# Code Knowledge Chain (CKC)
### Unified 3-Tier Knowledge Graph Orchestrator & Interactive UI for Codebases
*Based on the architecture from [Graphify vs GitNexus vs CodeGraph](https://vijayasekhar-deepak.beehiiv.com/p/graphify-vs-gitnexus-vs-codegraph) by Vijayasekhar Deepak.*

---

## The Core Philosophy: "Traverse ➔ Reason ➔ Explain"

Traditional AI coding assistants read repositories like books—from page one to the last page using `grep`, file lists, and raw file reading. On non-trivial codebases, this **"Search ➔ Read ➔ Guess"** loop burns tens of thousands of tokens and produces hallucinations.

Modern software systems are **networks, not flat documents**. This framework chains three complementary code intelligence engines to provide structured, layered context:

```
        ┌─────────────────────────────────────────────────────────┐
        │       User Query / Task / Refactor Specification        │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Tier 1: Broad Project Knowledge              │
        │                       (Graphify)                        │
        │  • Discovers architecture docs, ADRs, SQL schemas       │
        │  • Identifies system modules, communities, & God nodes  │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Tier 2: Execution & Impact Analysis          │
        │                       (GitNexus)                        │
        │  • AST-derived deterministic call graph (Tree-sitter)   │
        │  • Blast radius calculation & risk scoring              │
        │  • Directed execution flow tracing (A → B)              │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Tier 3: Symbol Navigation & Precision        │
        │                       (CodeGraph)                       │
        │  • Exact symbol signatures, line numbers, & code blocks │
        │  • Immediate caller/callee navigation                   │
        │  • Affected test suite discovery                        │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Tier 4: Grounded Synthesis Engine            │
        │  • Assembles token-efficient, high-density context      │
        │  • Eliminates "Search → Read → Guess"                   │
        └─────────────────────────────────────────────────────────┘
```

---

## 3-Engine Responsibilities

| Engine | Primary Strength | Storage / Backend | Target Questions |
| :--- | :--- | :--- | :--- |
| **Graphify** | Multi-Modal & Architecture | `graphify-out/graph.json` | *"How does the entire system fit together? Which docs/schemas belong to this module?"* |
| **GitNexus** | Structural AST & Blast Radius | `.gitnexus/` (KuzuDB) | *"What breaks if I change this function? Which execution paths are affected?"* |
| **CodeGraph** | Fast Symbols & Source Context | `.codegraph/` | *"Where is this function defined, what is its exact code, and which tests cover it?"* |

---

## Installation & Setup

```bash
# Clone or navigate to the repository
cd /Users/stephencheng/Projects/Playground/code-knowledge-chain

# Install locally in editable mode (installs CLI and UI server)
pip install -e .
```

Prerequisites (installed globally on your system):
- `graphify` (via `pip install graphifyy`)
- `gitnexus` (via `npm install -g gitnexus`)
- `codegraph` (via `npm install -g @colbymchenry/codegraph`)

---

## Web UI Dashboard

The package includes a full-featured, interactive single-page application dashboard built with FastAPI, Server-Sent Events (SSE), Mermaid.js, and Marked.

### Starting the Web UI
```bash
# Start the web UI on default port 8000
code-chain ui

# Or specify a custom port / host and open browser automatically
code-chain ui --port 8080 --open
```

Once running, navigate to `http://localhost:8000`.

### UI Features
1. **Sticky Repository Bar**:
   - Live repository path validation (rejects invalid paths or traversal attempts).
   - Instant quick-load chips for preset sample projects (`test-project` and `sample-service`).
   - Overall Readiness indicator badge (🟢 3/3 Engines Ready, 🟡 Partial, 🔴 Missing).
2. **Dashboard & Streaming Indexing Panel**:
   - Real-time status cards for each engine: node counts, edge counts, community clusters, and storage locations.
   - Option to toggle Fast AST indexing (`--code-only`) or Full Multi-modal extraction (ADRs, schemas, PDFs).
   - Live streaming terminal log powered by Server-Sent Events (SSE) with elapsed timer and auto-scroll.
   - **Cancellation Support**: "Cancel Indexing" button cleanly terminates active background analyzer jobs.
3. **Architecture & Feature Query Explorer**:
   - Search input with pre-populated architectural suggestion chips.
   - Grounded context synthesis formatted in rendered GitHub-flavored markdown.
   - One-click copy button (`📋 Copy LLM Prompt Context`) to immediately paste grounded context into Claude, ChatGPT, Cursor, or Gemini.
4. **Refactoring & Blast Radius Studio**:
   - Evaluates any function, method, or class.
   - Visual Risk Meter (LOW, MEDIUM, HIGH, CRITICAL).
   - Upstream Call Hierarchy tree (depth 1, 2, ...).
   - Affected test suites list.
   - Actionable 4-step refactoring checklist.
5. **Directed Execution Flow Tracer**:
   - Specify source and target symbols (`from_symbol` ➔ `to_symbol`).
   - Live interactive **Mermaid.js diagram** rendered directly in browser.
   - Step-by-step hop cards with file locations and domain tags.
6. **Artifacts Inspector**:
   - Lists generated graph outputs (`graphify-out/graph.json`, `GRAPH_REPORT.md`, `index_manifest.json`).
   - In-browser safe file reader with syntax formatting.

---

## CLI Usage

### 1. Indexing a Repository
```bash
# Index current directory across Graphify, GitNexus, and CodeGraph
code-chain init

# Index a specific target project
code-chain -p /path/to/project init

# Optional: enable LLM multimodal extraction for non-code files
code-chain -p /path/to/project init --multimodal
```

### 2. Checking Readiness & Status
```bash
code-chain -p /path/to/project status
```

### 3. Architecture & Feature Queries ("How does X work?")
```bash
code-chain -p /path/to/project query "user authentication and session validation"
```

### 4. Blast Radius & Refactor Analysis ("What breaks if I touch X?")
```bash
code-chain -p /path/to/project impact UserService.updateProfile
```

### 5. Deterministic Execution Tracing ("Trace execution from A to B")
```bash
code-chain -p /path/to/project trace handle_order_request process_payment
```

### 6. Git Diff Change Detection
```bash
code-chain -p /path/to/project diff
```

---

## Python API Usage

You can embed the chaining workflow directly into Python automation scripts or custom agent frameworks:

```python
from code_chain import CodeKnowledgeChain

# Connect to any project
chain = CodeKnowledgeChain(project_path="/path/to/project")

# Check status
status = chain.status()
print(f"Readiness: {status.ready_count}/3 engines ready")

# Query
query_res = chain.query("payment processing")
print(query_res.synthesized_context)

# Impact Analysis
impact_res = chain.impact("charge_customer")
print(f"Risk Level: {impact_res.risk_level}")
print(f"Blast Radius: {impact_res.blast_radius_count} components")
print(impact_res.synthesized_report)

# Execution Flow Trace
trace_res = chain.trace("api_handler", "db_save")
print(trace_res.synthesized_flow)
```

---

## MCP Server Integration (Model Context Protocol)

The tool includes a native JSON-RPC stdio MCP server that exposes the chained workflow directly to AI coding agents like **Claude Code**, **Cursor**, **Antigravity**, **Codex**, or **Windsurf**.

### Start the MCP Server
```bash
code-chain -p /path/to/project mcp
```

### Add to `mcp_config.json` (Antigravity / Claude Code / Cursor)
```json
{
  "mcpServers": {
    "code-knowledge-chain": {
      "command": "code-chain",
      "args": ["-p", "/path/to/your/project", "mcp"]
    }
  }
}
```

Exposed MCP Tools:
- `chain_status`: Check indexing health across Graphify, GitNexus, and CodeGraph.
- `chain_init`: Index a project across all 3 engines.
- `chain_query`: Query the 3-tier chained graph for feature understanding and architecture.
- `chain_impact`: Blast radius & refactor impact analysis with upstream call hierarchy and affected tests.
- `chain_trace`: Trace directed execution flow between two symbols.

---

## Fallback Behavior & Engine Resilience

The system is designed with graceful degradation:
- **If Graphify is missing or indexing is partial**: The pipeline still performs AST call graph exploration (GitNexus) and symbol exploration (CodeGraph), providing code-level context even without high-level documentation clusters.
- **If GitNexus is missing**: The pipeline falls back to Graphify's neighbor degree analysis and CodeGraph's direct callers/callees to estimate blast radius.
- **If CodeGraph is missing**: The pipeline relies on GitNexus AST symbol context and Graphify source links to locate code definitions.
- **UI Status Grid**: Clearly highlights partial readiness with color-coded badges (🟢 Ready, 🟡 Partial, 🔴 Missing) and detailed error diagnostics.

---

## Automated Test Suite

Run the full automated test suite (adapters, pipelines, MCP server, Web UI API, SSE streaming):

```bash
pytest tests -v
```

Output:
```
============================= 23 passed in 19.01s ==============================
```
