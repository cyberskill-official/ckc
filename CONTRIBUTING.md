# Contributing to Code Knowledge Chain (CKC)

Thank you for your interest in contributing to **Code Knowledge Chain**! CKC is a 3-tier hybrid code intelligence framework uniting **Graphify** (high-level structural & architectural mapping), **GitNexus** (execution graphs & blast radius analysis), and **CodeGraph** (fine-grained AST, symbol reference, and semantic graphs).

We welcome contributions of all kinds: bug fixes, documentation improvements, new pipeline steps, adapter enhancements, and UI features.

---

## Code of Conduct

Please review and adhere to our [Code of Conduct](CODE_OF_CONDUCT.md) in all project interactions.

---

## Development Setup

### Prerequisites

1. **Python 3.10+**
2. **Git**
3. **Node.js 18+** and **npm**
4. The three underlying graph engines:
   - **Graphify**: `pip install graphifyy`
   - **GitNexus**: `npm install -g gitnexus`
   - **CodeGraph**: `npm install -g @colbymchenry/codegraph`

### Editable install (recommended for contributors)

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
pytest tests -q
```

Dev extras install `pytest`, `ruff`, and `httpx` (see `pyproject.toml`).

### One-Click Setup

To configure your local environment, install dependencies in editable mode, initialize bundled sample repositories, run health checks, and start the UI:

```bash
# On macOS / Linux:
./setup.sh

# On Windows (PowerShell):
./setup.ps1

# Or via Python directly (cross-platform):
python3 scripts/setup.py
```

To run the setup without automatically launching the Web UI:
```bash
python3 scripts/setup.py --no-ui
```

---

## CI & branch protection

GitHub Actions runs Ruff + the pytest matrix on every push/PR to `main` (see `.github/workflows/ci.yml`).

**Platform support:** CI and primary development target **Linux and macOS**. Windows is used for setup scripts (`setup.ps1`) but is **not** covered by a GitHub Actions Windows job today — treat Windows as best-effort / unsupported for CI parity unless you add a matrix runner.

**Index timeout model (do not unify casually):**

| Surface | Semantics |
| --- | --- |
| UI `/api/index/stream` | One shared wall-clock deadline for Graphify + GitNexus + CodeGraph |
| CLI / MCP `IndexPipeline` | Each engine gets a full per-engine timeout |

UI argv builders in `server._build_index_steps` mirror adapter command helpers; a single shared streaming IndexPipeline is deferred to avoid argv drift regressions.

**Recommended repository settings** (GitHub → Settings → Branches → Branch protection rules for `main`):

- Require a pull request before merging
- Require status checks to pass: `Lint (Ruff)` and the `Test (...)` matrix jobs
- Do not allow force pushes to `main`

Branch protection itself requires org/repo admin and is intentionally not automated by CKC.

---

## Project Architecture

```
code-knowledge-chain/
├── examples/                      # Self-contained sample projects (Python, TypeScript)
├── scripts/
│   ├── setup.py                  # One-click cross-platform setup script
│   └── cleanup.py                # One-click cleanup and reset script
├── src/code_chain/
│   ├── adapters/                 # Adapter layer wrapping Graphify, GitNexus, CodeGraph
│   │   ├── base.py               # Abstract base adapter interface
│   │   ├── graphify_adapter.py   # High-level architecture & file graph adapter
│   │   ├── gitnexus_adapter.py   # Execution flow & call graph adapter
│   │   └── codegraph_adapter.py  # Precise AST & symbol reference adapter
│   ├── core/                     # Orchestrator, models, and configuration
│   ├── pipelines/                # Multi-engine synthesized workflows
│   │   ├── index_pipeline.py     # Parallel 3-engine indexing & manifest generation
│   │   ├── query_pipeline.py     # Tier-by-tier architecture & symbol search
│   │   ├── impact_pipeline.py    # Blast radius scoring & affected test calculation
│   │   └── trace_pipeline.py     # End-to-end execution path synthesis & Mermaid diagrams
│   ├── cli/                      # Rich-powered command-line interface
│   ├── mcp/                      # Model Context Protocol (MCP) server
│   └── ui/                       # Modern web dashboard (FastAPI + SSE streaming)
└── tests/                        # Comprehensive test suite (adapters, pipelines, UI, MCP)
```

---

## Testing & Quality

### Running Tests

Run the full automated test suite using `pytest`:

```bash
pytest tests -v
```

All tests run against self-contained sample repositories inside `examples/` and require zero mock servers or network access.

### Linting & Formatting

We maintain clean, PEP 8-compliant Python code:

```bash
# Check with ruff
ruff check .

# Format with ruff
ruff format .
```

---

## Cleanup & Local Reset

To clear temporary caches, bytecode, and test results:
```bash
# Light cleanup (caches and bytecode)
python3 scripts/cleanup.py -y

# Full reset (removes generated graph indexes and restores clean repo state)
python3 scripts/cleanup.py --all -y
```

---

## Pull Request Guidelines

1. **Branch Naming**: Use descriptive branch names like `feature/ast-filter` or `fix/gitnexus-path-encoding`.
2. **Atomic Commits**: Keep commits focused and provide descriptive commit messages.
3. **Tests**: Add test coverage for new functionality or regression tests for bug fixes.
4. **Clean Workspace**: Ensure `scripts/cleanup.py --all -y` leaves no uncommitted artifacts or machine-specific paths before opening a PR.
5. **PR Template**: Complete the fields in the PR template describing your changes and verification steps.
