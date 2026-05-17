<p align="center">
  <img src="img/contexty.png" alt="Contexty — Context-Life Mascot" width="480" />
</p>

<h1 align="center">Context-Life (CL)</h1>

<p align="center">
  <strong>LLM Context Optimization MCP Server</strong><br/>
  <em>Local RAG · Intelligent Trim · Token Counting · Prompt Caching · Context Health</em>
</p>

<p align="center">
  <a href="https://github.com/ErickGuerron/MCP-Context-Life/releases"><img src="https://img.shields.io/badge/version-0.8.7-blue?style=flat-square" alt="Version" /></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-%3E%3D3.10-brightgreen?style=flat-square" alt="Python" /></a>
  <a href="LICENSE.md"><img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/protocol-MCP-purple?style=flat-square" alt="MCP" /></a>
</p>

<p align="center">
  Zero API calls — everything runs locally on your machine.
</p>

---

## What is Context-Life?

Context-Life is an **MCP server** that optimizes how LLMs use their context window. Think of **Contexty** (our mascot) as a little helper that sits between your AI client and the model, making sure every token counts.

- **Token Counting** — Exact counts using tiktoken with LRU caching
- **Smart Trimming** — Intelligent message array optimization that never drops system instructions
- **Local RAG** — Semantic search over your files using LanceDB + multilingual embeddings
- **Prompt Caching** — Two-level prefix segmentation for maximum cache reuse
- **Context Health** — Real-time health score (0-100) with actionable recommendations
- **Orchestrator Detection** — Auto-detects Gentle AI, Engram, and MCP orchestrators
- **Intelligent Context Optimization** — Classifies prompts as LIGHT / REQUIRED / CRITICAL to decide when optimization is actually needed
- **HALT Governance** — Detects contradictions and halts before generating incompatible code
- **Auto-Invoke Cache** — TTL-based caching with SHA-256 key derivation and concurrent request deduplication
- **Cross-Session State** — SQLite journal for persistent state across sessions
- **Governance Dashboard** — Real-time metrics (cache status, priority tier, staleness)
- **Multi-Stack Detection** — Detects Cursor, Windsurf, and Codex environments

---

## Install

### Using Scoop (Windows — Recommended)

Scoop is the recommended installation method for Windows. It handles updates automatically and keeps everything under user control.

```bash
scoop bucket add context-life https://github.com/ErickGuerron/MCP-Context-Life
scoop install context-life
```

To update:
```bash
scoop update context-life
```

**Don't have Scoop?** Install it first (PowerShell):
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex
```

For full scoop documentation, visit [scoop.sh](https://scoop.sh).

---

### Using uv (Fastest)

```bash
uv tool install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

<details>
<summary>Don't have <code>uv</code>? Install it first</summary>

- **Windows:** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
- **macOS / Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
</details>

### Using pipx

```bash
pipx install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

### Standard pip

```bash
pip install git+https://github.com/ErickGuerron/MCP-Context-Life.git
```

### Install Profiles

```bash
# Full install (default — includes RAG)
uv tool install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"

# Core only (token counting + trim, no ML dependencies)
pip install "context-life[core]"

# With RAG (LanceDB + sentence-transformers)
pip install "context-life[rag]"

# Pinned to a specific version
uv tool install "git+https://github.com/ErickGuerron/MCP-Context-Life.git@v0.7.1"
```

### From Source

```bash
git clone https://github.com/ErickGuerron/MCP-Context-Life.git
cd MCP-Context-Life
pip install -e ".[dev]"
```

### Docker

```bash
docker build -t context-life .
docker run --rm context-life version
docker run --rm context-life info
docker run --rm context-life doctor
```

> [!WARNING]
> **Windows Users:** Windows locks running `.exe` files. If you get `[WinError 32]` during upgrade, close your MCP client first (OpenCode, Claude Desktop, Cursor, etc.).

---

## CLI Commands

```bash
context-life                           # Start MCP server (stdio)
context-life serve                     # Start MCP server (stdio)
context-life serve --http              # Start MCP server (HTTP)
context-life info                      # System info, config, dependencies
context-life doctor                    # Environment diagnostics
context-life warmup                    # Explain RAG warmup mode + current setting
context-life warmup set startup        # Persist warmup mode: lazy|startup|manual
context-life warmup interactive        # Interactive selector for warmup mode + prewarm
context-life prewarm                   # Explicitly warm the RAG model now
context-life upgrade                   # Upgrade to latest GitHub release
context-life upgrade --version v0.8.7  # Install specific version
context-life upgrade --dry-run         # Check without installing
context-life version                   # Show version
context-life help                      # Show help
```

---

## Setup with MCP Clients

### OpenCode

Add to `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "context-life": {
      "type": "local",
      "command": ["context-life"],
      "enabled": true
    }
  }
}
```

To make the client run Context-Life automatically on every turn, add a first-step policy in your agent/system prompt that calls `preflight_request` before planning or answering.

```text
Before every user turn, call the Context-Life MCP prompt `preflight_request` with the raw user request, then follow the returned `applied_process`.
```

If you want to bake it into OpenCode, add the same rule to the primary agent prompt:

```text
Always call `preflight_request` before planning the response to any user message. If the result says `noop`, answer normally. If it recommends another step, follow `applied_process` exactly.
```

### Install from the TUI

Open `context-life tui`, go to **Config → Install Context-Life**, and choose one of:

- **OpenCode**
- **Antigravity**
- **Visual Studio Code**

Each option adds only the `context-life` MCP entry to that tool’s config.

For automatic preflight, the client must be configured to call `preflight_request` first; the server cannot intercept chat invisibly on its own.

Suggested Antigravity instruction:

```text
Before answering any user message, call the Context-Life MCP prompt `preflight_request` with the raw prompt. Use the returned `applied_process` to decide whether to optimize, search context, or continue normally.
```

### Claude Desktop

Edit `claude_desktop_config.json`:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "context-life": {
      "command": "context-life",
      "args": [],
      "env": {}
    }
  }
}
```

### Cursor / Windsurf / Gemini CLI

```json
{
  "mcpServers": {
    "context-life": {
      "command": "context-life"
    }
  }
}
```

---

## Features

### Tools

| Tool | Description |
|------|-------------|
| `autoinvoke_context` | Auto-invoke context optimization at prompt boundaries (zero-step wake for solo-agents) |
| `sleep_context` | Persist session learnings at task end (solo-agent sleep behavior) |
| `count_tokens_tool` | Count tokens for any text using tiktoken |
| `count_messages_tokens_tool` | Count tokens for OpenAI-style message arrays |
| `optimize_messages` | Trim message arrays using tail/head/smart strategies |
| `search_context` | Semantic search over indexed local knowledge |
| `index_knowledge` | Index local files into LanceDB for RAG retrieval |
| `cache_context` | Cache-aware message processing with segmented prefixes |
| `rag_stats` | Knowledge base statistics |
| `clear_knowledge` | Clear all indexed knowledge |
| `reset_token_budget` | Reset token budget tracker |
| `analyze_context_health_tool` | Context health analysis with score, metrics & recommendations |
| `get_orchestration_advice` | Actionable next-step contract for Gentle AI / MCP orchestrators |

### Resources

| Resource | Description |
|----------|-------------|
| `status://token_budget` | Current token budget + LRU cache stats |
| `cache://status` | Prompt cache hit/miss performance |
| `rag://stats` | RAG knowledge base info |
| `status://orchestrator` | Detected orchestrator & advisor mode status |
| `status://orchestration` | Static orchestration contract and recommended tool flow |

---

## Architecture

```
┌──────────────────────────────────────────────────┐
│            MCP Client (LLM Host)                 │
│    (OpenCode / Claude / Cursor / Gemini CLI)     │
└────────────────────┬─────────────────────────────┘
                     │ MCP Protocol (stdio/http)
┌────────────────────▼─────────────────────────────┐
│              Context-Life Server                  │
│                                                   │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Config       │  │ Token Counter            │  │
│  │ (3-tier)     │  │ (tiktoken + LRU cache)   │  │
│  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Trim History │  │ Cache Manager            │  │
│  │ (tail/head/  │  │ (2-level prefix +        │  │
│  │  smart)      │  │  advisor hints)          │  │
│  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ RAG Engine   │  │ Context Health           │  │
│  │ (LanceDB +   │  │ (score 0-100 +           │  │
│  │  lazy load)  │  │  recommendations)        │  │
│  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Orchestrator │  │ CLI (Rich TUI)           │  │
│  │ Detector     │  │ (info/doctor/upgrade/    │  │
│  │ (auto-sense) │  │  version)                │  │
│  └──────────────┘  └──────────────────────────┘  │
└───────────────────────────────────────────────────┘
```

Composition now starts in `mmcp/presentation/mcp/server.py`, which wires MCP tools/resources to `mmcp/presentation/app_container.py`. The container owns the shared runtime objects and config-aware accessors, so the server can stay thin while preserving the public MCP surface.

### Layer map

- `mmcp/presentation/` — MCP + CLI entry adapters and composition root
- `mmcp/application/` — vertical slices and ports
- `mmcp/infrastructure/` — concrete adapters by responsibility (`environment/`, `persistence/`, `tokens/`, `knowledge/`, `context/`, `telemetry/`)
- `mmcp/domain/` — reserved for pure rules if they are extracted later

---

## How It Works

### Token Counter
Uses `tiktoken` for exact token counting. Supports `cl100k_base` (GPT-4, Claude), `o200k_base` (GPT-4o), and `p50k_base` (Codex). **v0.5.0:** LRU cache (1024 entries) eliminates redundant counts during trim iterations.

### Trim History
Three strategies with **strict budget guarantee**:
- **tail**: Keep the most recent messages
- **head**: Keep the oldest messages
- **smart**: Protect system messages + recent turns, compress the middle. If anchors exceed budget, compacts into a policy digest.

### RAG Engine
Local vector search using **LanceDB** (serverless) + **paraphrase-multilingual-MiniLM-L12-v2** (multilingual embeddings). **v0.5.0:** Lazy model loading eliminates cold start latency — the embedding model loads only on first use.

> [!WARNING]
> If you're seeing ~30s delays when opening your AI client (OpenCode, Claude Desktop, etc.) for the first time after a cold start, it's the embedding model loading. Run `context-life warmup set startup` to pre-warm it at MCP boot, or `context-life prewarm` before opening your client.
- Automatic deduplication by file hash
- Token-budgeted retrieval with skip-and-continue packing
- Per-source chunk limits (`max_chunks_per_source`)
- Score filtering (`min_score`)

### Cache Manager
Two-level prefix segmentation for optimal cache reuse:
- **Base prefix**: system/developer instructions (stable across turns)
- **RAG prefix**: injected knowledge context (may change)
- When only RAG changes, base prefix cache is preserved
- **v0.5.0:** Advisor hints injected when an AI orchestrator is detected

### Context Health *(v0.5.0)*
Real-time diagnostic tool that computes a health score (0-100) based on:
- Token utilization (% of budget consumed)
- Message redundancy (duplicate detection)
- System-to-user ratio (prompt domination)
- Noise estimation (trivial/empty messages)

Returns actionable recommendations and orchestrator hints for proactive context management.

### Orchestrator Detection *(v0.5.0)*
Auto-detects when CL runs alongside AI orchestrators like Gentle AI or Engram:
- **Environment variables**: `GENTLE_AI_ACTIVE`, `ENGRAM`, `MCP_ORCHESTRATOR`
- **Workspace artifacts**: `.gemini/`, `.gga`, `.agent/`, `.agents/`
- Enables "Advisor Mode" with proactive optimization hints

> **[Orchestrator Integration Guide](docs/orchestrator-integration.md)** — Context flow, Gentle AI / SDD integration, and adapter configuration.

### Intelligent Context Optimization *(v0.7.1)*
D4 evaluates every prompt and classifies it as LIGHT / REQUIRED / CRITICAL:
- **LIGHT** (confidence ≥ 0.80): Prompt is clear — continue without optimization
- **REQUIRED** (confidence 0.55-0.79): Prompt needs restructuring or context — call `cache_context` only if needed
- **CRITICAL** (any conflict): Contradiction detected — **HALT** and resolve before proceeding

The orchestrator receives both the legacy contract (`intent`, `keywords`, `advice`) and the D4 decision under `d4{}`, so existing workflows are preserved while gaining intelligent routing.

> **[Context Optimization Logic](docs/context-optimization.md)** — Business rules, state definitions, confidence thresholds, HALT triggers, and token cost analysis.

### Auto-Invoke Context Lifecycle *(v0.7.1)*

Context-Life implements a **Zero-Step** context lifecycle — context optimization happens *before* any core agent task execution:

**Solo-Agent (Windsurf, Codex, Claude Code):**
- **Wake (step zero)**: `autoinvoke_context` is called as the absolute first token before the agent thinks
- **Sleep (task end)**: `sleep_context` persists learnings to the server
- Governance is enforced via the `context-life` skill file

**Orchestrator (Gentle AI / custom with `delegate()`):**
- The orchestrator routes every prompt to `context-life-advisor` first
- Advisor calls `autoinvoke_context` and returns a `ContextPack` with ground truth
- Governance is handled by the orchestrator's routing rules

**Bypass:** Set `DISABLE_AUTOINVOKE=1` in the environment to disable all auto-invocation behavior.

| Environment | Governance | Wake | Sleep |
|------------|------------|------|-------|
| solo-agent | Skill file | `autoinvoke_context` as step zero | `sleep_context` at task end |
| gentle-ai / orchestrator with `delegate()` | Orchestrator routing | `context-life-advisor` sub-agent | Handled via orchestrator phases |
| solo-agent (`DISABLE_AUTOINVOKE=1`) | None | No-op | No-op |

### Orchestration Advice *(vNext)*
Context-Life now exposes a first explicit orchestration contract for upstream orchestrators:
- `get_orchestration_advice` combines health + detection into actionable next steps
- `status://orchestration` advertises capabilities and a recommended tool flow
- Current integration level remains **heuristic-advisor** (not a bidirectional handshake yet)

---

## Configuration

Context-Life uses a three-tier configuration system:

1. **Built-in defaults** — always available
2. **Config file** — `~/.config/context-life/config.toml` (Linux/macOS) or `%APPDATA%\context-life\config.toml` (Windows)
3. **Environment variables** — `CL_*` prefix (highest priority)

### Config file example

```toml
[rag]
top_k = 5
min_score = 0.3
max_chunks_per_source = 3
chunk_size = 512
warmup_mode = "lazy"

[token_budget]
default = 128000
safety_buffer = 500

[trim]
preserve_recent = 6

[paths]
data_dir = "~/.local/share/context-life"
```

### Environment variables

```bash
export CL_RAG_TOP_K=10
export CL_RAG_WARMUP_MODE=startup
export CL_TOKEN_BUDGET_DEFAULT=64000
export CL_DATA_DIR=/custom/path
```

### RAG warmup modes

- `lazy` *(default)* — fast MCP startup, but the first RAG search/index pays the model load cost.
- `startup` — slower MCP startup because the model is prewarmed during boot, but first RAG use is faster.
- `manual` — never prewarms automatically; use `context-life prewarm` or the `prewarm_rag` MCP tool when you want to warm it explicitly.

If you prefer not to memorize commands, run `context-life warmup interactive` or open `context-life tui` and choose **RAG Warmup Selector**. From there you can inspect MCP impact, switch between `lazy` / `startup` / `manual`, and optionally trigger a manual prewarm immediately.

---

## Development

```bash
# Run with HTTP transport for testing
context-life serve --http

# Or from source
python -m mmcp serve --http

# Lint
ruff check mmcp/

# Test
pytest

# Skip slow RAG integration tests
pytest -m "not slow"

# Run performance-oriented smoke/stress tests
pytest -m performance
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Context Optimization Logic](docs/context-optimization.md) | Business rules and behavior of the intelligent prompt optimization system (LIGHT/REQUIRED/CRITICAL states, confidence scoring, HALT governance) |
| [Orchestrator Integration Guide](docs/orchestrator-integration.md) | How Context-Life integrates with Gentle AI and other orchestrators, context flow, and adapter configuration |
| [Installation Guide](docs/installation.md) | Complete installation instructions for all platforms (Scoop, uv, pipx, pip, Docker) |

## Requirements

- Python >= 3.10
- ~500MB disk for sentence-transformers model (downloaded once on first use)
- No GPU required — runs on CPU

## License

[MIT License](LICENSE.md)

---

<p align="center">
  <sub>Built by <a href="https://github.com/ErickGuerron">Erick Guerrón</a></sub>
</p>
