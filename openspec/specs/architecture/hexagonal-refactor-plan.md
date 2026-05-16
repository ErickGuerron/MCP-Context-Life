# Context-Life Hexagonal Refactor Plan

## Goal

Move Context-Life toward **Hexagonal Architecture** with **Vertical Slices** inside the application layer, without breaking current MCP behavior.

## Current Position

| Area | Status | Notes |
|---|---|---|
| Composition root boundary | ✅ Done | `mmcp/presentation/app_container.py` owns shared runtime objects |
| `server.py` thinning | ✅ Done | `mmcp/presentation/mcp/server.py` is now mostly routing/wiring |
| Architecture note in README | ✅ Done | Short note added for the new boundary |
| Container tests | ✅ Done | Basic safety net added |
| Explicit ports/adapters | ✅ Done | Token counter and prefix cache ports added |
| Vertical slices | ✅ Done (phase 1) | `tokens` slice created and wired |
| Context slice | ✅ Done (phase 2) | Trim and cache orchestration moved behind a context application service |
| Telemetry slice | ✅ Done (phase 5) | Payload mapping and persistence now live behind a telemetry boundary |
| CLI adapter cleanup | ✅ Done (phase 6) | Command parsing now lives in an application feature boundary |
| Final consolidation | ✅ Done (phase 7) | Compatibility shims removed; tests now target the application boundary directly |

## Target Architecture

```text
mmcp/
├── domain/
├── application/
│   ├── ports/
│   └── features/
│       ├── tokens/
│       ├── context/
│       ├── knowledge/
│       ├── telemetry/
│       └── cli/
├── infrastructure/
│   ├── environment/
│   ├── persistence/
│   ├── tokens/
│   ├── knowledge/
│   ├── context/
│   └── telemetry/
└── presentation/
    ├── app_container.py
    ├── mcp/
    └── cli/
```

## Migration Plan

| Phase | Status | What happens | Outcome |
|---|---|---|---|
| 0. Composition root | ✅ Done | Extract shared runtime ownership into `app_container.py` | A stable boundary exists |
| 1. Ports first | ✅ Done | Define narrow ports for token counting and cache persistence | Core stops depending on concrete infra |
| 2. Tokens slice | ✅ Done | Move token counting/budget logic behind the ports | Smallest feature slice becomes hexagonal |
| 3. Context slice | ✅ Done | Extract trim/cache behavior into a dedicated slice | Context logic stops living in shared modules |
| 4. Knowledge slice | ✅ Done | Separate RAG indexing/search/prewarm behind an application service boundary | RAG tools stay stable |
| 5. Telemetry slice | ✅ Done | Isolated telemetry mapping/persistence behind a boundary | Metrics changes stop spreading everywhere |
| 6. CLI adapter cleanup | ✅ Done | Keep CLI as adapter only | UI/runtime concerns stop mixing |
| 7. Final consolidation | ✅ Done | Remove compatibility glue and tighten contracts | Structure is visibly hexagonal |

## Detailed Work Items

### 1) Ports First

- [x] Define a token counting port.
- [x] Define a cache/session store port.
- [x] Define a knowledge store/search port.
- [x] Stop application logic from importing concrete infra directly (for tokens/cache).

### 2) Tokens Slice

- [x] Move token budget behavior into a `tokens` feature slice.
- [x] Keep encoding/counting behind a port.
- [x] Preserve current tool names and outputs.

### 3) Context Slice

- [x] Extract trim logic into a `context` slice.
- [x] Move cache orchestration into the same boundary or a sibling slice.
- [x] Keep budget enforcement behavior unchanged.

### 4) Knowledge Slice

- [x] Split RAG indexing/search/prewarm into use cases.
- [x] Push the RAG engine behind a knowledge store adapter.
- [x] Keep lazy loading and warmup behavior stable.

### 5) Telemetry Slice

- [x] Separate payload mapping from persistence.
- [x] Inject the store instead of resolving it internally.
- [x] Preserve current telemetry contracts.

### 6) CLI Adapter Cleanup

- [x] Keep CLI commands as thin adapters.
- [x] Remove feature logic from command handlers where possible.

### 7) Final Consolidation

- [x] Remove safe compatibility glue from the container/server boundary.
- [x] Tighten tests so they target application modules directly.
- [x] Preserve public MCP tool names, CLI commands, and JSON outputs.

## Success Criteria

| Criterion | Meaning |
|---|---|
| Core depends on ports | Application code no longer imports concrete infra directly |
| Tools stay stable | MCP tool names and outputs do not change |
| Slices are visible | Tokens, context, knowledge, and telemetry each have clear homes |
| Tests remain green | Behavior stays covered during migration |
| Docs stay current | README/docs only describe current behavior |

## Notes

- This is a **migration**, not a rewrite.
- The first seam is already done.
- The next step is to continue with the `context` slice and then `knowledge`/`telemetry`.
- Batch 1 restored visible `infrastructure/` and `presentation/` layer folders; compatibility shims were removed, leaving only the package entrypoint `mmcp/__main__.py`.
