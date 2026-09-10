# Code Knowledge Chain (CKC) Pipelines
This document defines each pipeline's contract using the ICM (Interpretable Context Methodology) Stage Contracts pattern, breaking down Inputs, Process, and Outputs.

## Index Pipeline (`code-chain init`)

### Inputs
| Source | Data | Why |
|--------|------|-----|
| Target project directory | Source code files | AST parsing and graph construction |
| Existing graph indexes | `graphify-out/`, `.gitnexus/`, `.codegraph/` | Skip re-indexing if present (unless --force) |
| Documentation files | `.md`, `.rst`, `.adoc` files | Local docs overlay for code-only mode |

### Process
1. Run Graphify extract (default: `--code-only` AST mode)
2. Build local docs overlay (`.code_chain/docs_index.json`)
3. Run GitNexus index (Tree-sitter AST + KuzuDB)
4. Run CodeGraph index (symbol extraction)
5. Write index manifest (`.code_chain/index_manifest.json`)

### Outputs
| Artifact | Location | Format |
|----------|----------|--------|
| Architecture graph | `graphify-out/graph.json` | JSON (nodes + edges + communities) |
| Docs overlay | `.code_chain/docs_index.json` | JSON (heading-chunked doc entries) |
| AST database | `.gitnexus/` | KuzuDB |
| Symbol index | `.codegraph/` | CodeGraph internal format |
| Index manifest | `.code_chain/index_manifest.json` | JSON (timing, status, engine details) |

## Query Pipeline (`code-chain query`)

### Inputs
| Source | Data | Why |
|--------|------|-----|
| User query | Natural language string | Defines the architectural concept or feature to investigate |
| Graphify indexes | `graphify-out/` | Retrieve high-level architecture and cross-domain entities |
| GitNexus indexes | `.gitnexus/` | Retrieve AST execution flows and structural dependencies |
| CodeGraph indexes | `.codegraph/` | Retrieve symbol definitions and verbatim source snippets |

### Process
1. Query Tier 1 (Graphify) for architectural context and entity relations.
2. Query Tier 2 (GitNexus) to map execution flows based on Tier 1 results.
3. Query Tier 3 (CodeGraph) to fetch precise symbol definitions and source blocks.
4. (Optional) Synthesize results using local LLM / OpenAI-compatible endpoint.

### Outputs
| Artifact | Content | Format |
|----------|---------|--------|
| Query Result | Stacked markdown with per-tier sections and reading guide | Markdown |
| JSON Dump | Raw structured payload of all tier responses and engine errors | JSON (with `--json`) |

## Impact Pipeline (`code-chain impact`)

### Inputs
| Source | Data | Why |
|--------|------|-----|
| Target symbol | Function, class, or method name | Defines the origin point for blast radius analysis |
| GitNexus indexes | `.gitnexus/` | Trace upstream callers, dependencies, and affected tests |
| CodeGraph indexes | `.codegraph/` | Fetch source context for affected symbols |

### Process
1. Locate the target symbol in Tier 3 (CodeGraph).
2. Trace upstream callers and dependencies using Tier 2 (GitNexus).
3. Identify impacted business processes and tests.
4. (Optional) Synthesize a step-by-step refactoring plan via LLM.

### Outputs
| Artifact | Content | Format |
|----------|---------|--------|
| Impact Report | Blast radius, upstream callers, impacted tests, refactoring plan | Markdown |
| JSON Dump | Structured blast radius payload | JSON (with `--json`) |

## Trace Pipeline (`code-chain trace`)

### Inputs
| Source | Data | Why |
|--------|------|-----|
| Source symbol | Function/symbol name | Start node of the trace path |
| Destination symbol | Function/symbol name | End node of the trace path |
| GitNexus indexes | `.gitnexus/` | Resolve exact directed execution paths |

### Process
1. Verify existence of both source and destination symbols.
2. Query Tier 2 (GitNexus) for directed execution paths (shortest path / all paths) between the two symbols.
3. Fetch relevant code snippets from Tier 3 (CodeGraph) for hops.
4. (Optional) Generate hop sequence diagram and synthesis via LLM.

### Outputs
| Artifact | Content | Format |
|----------|---------|--------|
| Trace Flow | Directed execution path, hop sequence, and diagram | Markdown |
| JSON Dump | Structured flow path payload | JSON (with `--json`) |

## Diff Pipeline (`code-chain diff`)

### Inputs
| Source | Data | Why |
|--------|------|-----|
| Git Workspace | Uncommitted/staged diffs | Identify modified code hunks |
| GitNexus indexes | `.gitnexus/` | Map hunks to indexed symbols and flows |

### Process
1. Extract current git diff hunks from the workspace.
2. Map changed lines to AST nodes using Tier 2 (GitNexus detect-changes).
3. Identify affected execution flows and symbols.

### Outputs
| Artifact | Content | Format |
|----------|---------|--------|
| Diff Map | Mapping of diff hunks to affected symbols and execution flows | JSON |
