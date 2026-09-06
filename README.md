# Code Knowledge Chain (CKC)
### Unified 3-Tier Knowledge Graph Orchestrator for Codebases
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

## Installation

```bash
# Clone or navigate to the repository
cd /Users/stephencheng/Projects/Playground/code-knowledge-chain

# Install locally in editable mode
pip install -e .
```

Prerequisites (installed globally on your system):
- `graphify` (via `pip install graphifyy`)
- `gitnexus` (via `npm install -g gitnexus`)
- `codegraph` (via `npm install -g @colbymchenry/codegraph`)

---

## CLI Usage

### 1. Indexing a Repository
To initialize and build all 3 knowledge graphs for any target repository:
```bash
# Index current directory
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
Output:
```markdown
# Code Knowledge Chain Status: `my-project`
**Path:** `/path/to/project`

| Engine | Layer | Status | Nodes | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Graphify** | Multi-Modal & Architecture | ✅ Ready | 24 | 3 communities |
| **GitNexus** | AST & Execution Flows | ✅ Ready | 38 | KuzuDB graph |
| **CodeGraph** | Symbols & Test Impact | ✅ Ready | 42 | Fast symbol cache |

**Overall Readiness:** 3/3 engines indexed.
```

### 3. Architecture & Feature Queries ("How does X work?")
Performs cross-domain doc matching, maps execution flows, and retrieves verbatim source blocks:
```bash
code-chain -p /path/to/project query "user authentication and session validation"
```

### 4. Blast Radius & Refactor Analysis ("What breaks if I touch X?")
Calculates exact risk level, upstream caller hierarchy, affected business processes, and affected test suites:
```bash
code-chain -p /path/to/project impact UserService.updateProfile
```

### 5. Deterministic Execution Tracing ("Trace execution from A to B")
Computes the shortest directed call chain between two functions and emits a Mermaid diagram:
```bash
code-chain -p /path/to/project trace handle_order_request process_payment
```

### 6. Git Diff Change Detection
Maps uncommitted git hunks directly to indexed knowledge graph entities:
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

### Exposed MCP Tools:
- `chain_status`: Check indexing health across Graphify, GitNexus, and CodeGraph.
- `chain_init`: Index a project across all 3 engines.
- `chain_query`: Query the 3-tier chained graph for feature understanding and architecture.
- `chain_impact`: Blast radius & refactor impact analysis with upstream call hierarchy and affected tests.
- `chain_trace`: Trace directed execution flow between two symbols.

---

## Real-World Workflow Scenarios

### Scenario A: Architectural Onboarding
*   **Challenge:** A new developer or AI agent joins a 500k-line repo.
*   **Without CKC:** Searches filenames, opens 30 files, burns 80,000 tokens guessing relations.
*   **With CKC:** Runs `code-chain query "authentication workflow"`. In seconds, receives the matching architecture docs (Graphify), the execution call chain (GitNexus), and the exact line-numbered source code (CodeGraph).

### Scenario B: Refactoring with Confidence
*   **Challenge:** Modifying a core database model or shared service.
*   **Without CKC:** Unseen downstream regressions discovered only after staging deployment.
*   **With CKC:** Runs `code-chain impact PaymentService.charge`. Receives a deterministic blast radius report, all upstream callers by depth, impacted business processes, and the exact unit test files to run.

### Scenario C: Production Incident Tracing
*   **Challenge:** Sentry alerts show an error deep in the database layer initiated from a public API route.
*   **Without CKC:** Detective work manually tracing 10+ intermediate function calls.
*   **With CKC:** Runs `code-chain trace ApiRouter.handlePost DatabaseClient.save`. Receives the exact 4-hop execution chain with an interactive Mermaid sequence diagram.

---

## Verification & Testing

To run the automated test suite:
```bash
cd /Users/stephencheng/Projects/Playground/code-knowledge-chain
pytest tests -v
```
All tests verify:
- Individual adapter operations (`GraphifyAdapter`, `GitNexusAdapter`, `CodeGraphAdapter`).
- End-to-end multi-engine indexing (`IndexPipeline`).
- 3-tier chained querying (`QueryPipeline`).
- Blast radius and refactor reporting (`ImpactPipeline`).
- Execution path tracing (`TracePipeline`).
- MCP JSON-RPC 2.0 handshake and tool execution.
