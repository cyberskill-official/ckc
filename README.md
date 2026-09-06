# Code Knowledge Chain (CKC)
### Unified 3-Tier Knowledge Graph Orchestrator & Interactive UI for Codebases
*Based on the architecture from [Graphify vs GitNexus vs CodeGraph](https://vijayasekhar-deepak.beehiiv.com/p/graphify-vs-gitnexus-vs-codegraph) by Vijayasekhar Deepak.*

---

## The Core Philosophy: "Traverse ➔ Reason ➔ Explain"

Traditional AI coding assistants read repositories like books—from page one to the last page using `grep`, file lists, and raw file reading. On non-trivial codebases, this **"Search ➔ Read ➔ Guess"** loop burns tens of thousands of tokens and produces hallucinations.

Modern software systems are **networks, not flat documents**. This framework chains three complementary code intelligence engines to provide structured, layered context:

**Default stack (no API key required):**
- **Graphify** runs in `--code-only` (AST) mode by default
- A **local docs overlay** (`.code_chain/docs_index.json`) indexes markdown / rst / adoc so docs still appear in search without multimodal LLM extract
- **GitNexus** + **CodeGraph** supply AST flows and symbol precision
- **Optional LM Studio** (or any OpenAI-compatible `/v1`) can append a short synthesis section when `CKC_LLM_BASE_URL` / `OPENAI_BASE_URL` is set — use `--no-llm` to skip
- **`--multimodal`** remains the opt-in Graphify path for semantic doc/image edges (works with LM Studio via `OPENAI_BASE_URL`)

```
        ┌─────────────────────────────────────────────────────────┐
        │       User Query / Task / Refactor Specification        │
        └────────────────────────────┬────────────────────────────┘
                                     │
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │            Tier 1: Broad Project Knowledge              │
        │           (Graphify + local docs overlay)               │
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
        │  • Assembles token-budgeted stacked markdown            │
        │  • Optional local LM Studio / OpenAI-compatible chat    │
        └─────────────────────────────────────────────────────────┘
```

---

## 3-Engine Responsibilities

| Engine | Primary Strength | Storage / Backend | Target Questions |
| :--- | :--- | :--- | :--- |
| **Graphify** | Architecture graph (default `--code-only`) | `graphify-out/graph.json` | *"How does the system fit together?"* |
| **Local docs overlay** | Markdown / docs without multimodal LLM | `.code_chain/docs_index.json` | *"Which ADRs or ARCH docs mention this module?"* |
| **GitNexus** | Structural AST & Blast Radius | `.gitnexus/` (KuzuDB) | *"What breaks if I change this function?"* |
| **CodeGraph** | Fast Symbols & Source Context | `.codegraph/` | *"Where is this defined, and which tests cover it?"* |
| **Optional LLM** | Short local synthesis (LM Studio) | `CKC_LLM_*` / `OPENAI_*` env | *"Summarize the stacked context for me."* |

---

## Quickstart: One-Click Setup

Code Knowledge Chain includes automated, cross-platform setup and cleanup scripts that validate prerequisites, configure dependencies, initialize sample repositories, index all three engines, run health checks, and start the Web UI.

### Option A: One-Click Scripts
```bash
# macOS & Linux:
./setup.sh

# Windows (PowerShell):
./setup.ps1

# Or run with Python directly (cross-platform):
python3 scripts/setup.py
```
> **Flags**:
> - `--no-ui`: Run prerequisites, editable install, sample indexing, and tests without launching the Web UI.
> - `--port <PORT>`: Specify a custom port (default: 8000).
> - `--force`: Force re-indexing of sample repositories.

### Option B: Via CLI
```bash
pip install -e .
code-chain setup --no-ui
```

### One-Click Cleanup & Reset
```bash
# Light cleanup (removes caches, temporary test artifacts, and bytecode):
./cleanup.sh -y

# Full reset (stops background daemons, cleans all graph indexes, manifests, and temporary artifacts):
./cleanup.sh --all -y

# Windows (PowerShell):
./cleanup.ps1 -All -Yes

# Or via Python directly:
python3 scripts/cleanup.py --all -y
```

---

## Prerequisites (Graph Engines)

Code Knowledge Chain orchestrates three engines installed globally on your machine:
- **Graphify**: `pip install graphifyy`
- **GitNexus**: `npm install -g gitnexus`
- **CodeGraph**: `npm install -g @colbymchenry/codegraph`

*The one-click setup script will detect and attempt to automatically install any missing engines.*

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
   - Instant quick-load chips for preset sample projects (`python-auth-service` and `ts-billing-service`).
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
# Default: Graphify --code-only + local docs overlay (no API key)
code-chain init

# Index a specific target project
code-chain -p /path/to/project init

# Optional: enable Graphify multimodal extract for semantic doc/image edges
# (works with LM Studio if OPENAI_BASE_URL points at http://127.0.0.1:1234/v1)
code-chain -p /path/to/project init --multimodal
```

### 2. Checking Readiness & Status
```bash
code-chain -p /path/to/project status
```

### 3. Architecture & Feature Queries ("How does X work?")
```bash
code-chain -p /path/to/project query "user authentication and session validation"

# Skip optional LM Studio synthesis even if CKC_LLM_BASE_URL is set
code-chain -p /path/to/project query "auth" --no-llm
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

### Optional local model (LM Studio)
Copy `.env.example` and point at your OpenAI-compatible server:
```bash
export CKC_LLM_BASE_URL=http://127.0.0.1:1234/v1
export CKC_LLM_MODEL=your-loaded-model
export CKC_LLM_API_KEY=lm-studio
```
When configured, `query` / `impact` / `trace` append a **Local model synthesis** section. Soft-fails if the server is down; use `--no-llm` to disable.

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
pytest tests -q
```

LLM tests mock HTTP — no live LM Studio required. Integration tests on `examples/python-auth-service` expect the sample graphs to already be indexed (via `code-chain setup` or `init`).
