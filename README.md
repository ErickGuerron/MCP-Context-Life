# Context-Life (CL) — LLM Context Optimization MCP Server

> MCP server for LLM context optimization with local RAG, intelligent trim history, token counting, and prompt caching.
> Zero API calls — everything runs locally on your machine.

## Install

### Using uv (Fastest & Recommended)

`uv` is an extremely fast Python package installer that seamlessly manages isolated CLI tools across Windows, macOS, and Linux without affecting your system Python environment.

```bash
uv tool install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

### Using pipx (Standard isolated install)

Like `uv`, `pipx` installs the tool in an isolated sandbox, avoiding dependency conflicts.

```bash
pipx install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

### Note for Windows Users
> [!WARNING]
> Windows locks running `.exe` files. If you get a `[WinError 32]` when trying to upgrade or reinstall, it means the `context-life` server is currently running. **You must close your MCP client (OpenCode, Claude Desktop, Cursor, etc.) or stop any running terminal instances of context-life before running an upgrade command.**

### Standard pip (For Virtual Environments)

```bash
pip install git+https://github.com/ErickGuerron/MCP-Context-Life.git
```

### Install Profiles

```bash
# Full install (default — includes RAG)
pipx install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"

# Core only (token counting + trim, no ML dependencies)
pipx install "context-life[core]"

# With RAG (LanceDB + sentence-transformers)
pipx install "context-life[rag]"

# Pinned to a specific version
pipx install "git+https://github.com/ErickGuerron/MCP-Context-Life.git@v0.3.1"
```

### From source (for development)

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

## CLI Commands

```bash
context-life                           # Start MCP server (stdio)
context-life serve                     # Start MCP server (stdio)
context-life serve --http              # Start MCP server (HTTP)
context-life info                      # System info, config, dependencies
context-life doctor                    # Environment diagnostics
context-life upgrade                   # Upgrade to latest GitHub release
context-life upgrade --version v0.3.1  # Install specific version
context-life upgrade --dry-run         # Check without installing
context-life version                   # Show version
context-life help                      # Show help
```

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
export CL_TOKEN_BUDGET_DEFAULT=64000
export CL_DATA_DIR=/custom/path
```

## Setup with MCP Clients

### OpenCode

Add to your `~/.config/opencode/opencode.json`:

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

## Features

| Feature | Tool / Resource | Description |
|---------|----------------|-------------|
| Token Counter | `count_tokens_tool` | Count tokens for any text using tiktoken |
| Messages Counter | `count_messages_tokens_tool` | Count tokens for OpenAI-style message arrays |
| Trim History | `optimize_messages` | Trim message arrays using tail/head/smart strategies |
| RAG Search | `search_context` | Semantic search over indexed local knowledge |
| Index Files | `index_knowledge` | Index local files into LanceDB for RAG retrieval |
| Cache Context | `cache_context` | Cache-aware message processing with segmented prefixes |
| RAG Stats | `rag_stats` | Knowledge base statistics |
| Clear Knowledge | `clear_knowledge` | Clear all indexed knowledge |
| Reset Budget | `reset_token_budget` | Reset token budget tracker |
| Token Budget | `status://token_budget` | Check current token budget consumption |
| Cache Status | `cache://status` | View prompt cache hit/miss stats |
| RAG Stats | `rag://stats` | RAG knowledge base info |

## Architecture

```
┌──────────────────────────────────────────┐
│           MCP Client (LLM Host)          │
│   (OpenCode / Claude / Cursor / etc)     │
└─────────────────┬────────────────────────┘
                  │ MCP Protocol (stdio)
┌─────────────────▼────────────────────────┐
│           Context-Life Server            │
│  ┌─────────────┐  ┌───────────────────┐  │
│  │ Config      │  │ Token Counter     │  │
│  │ (3-tier)    │  │ (tiktoken)        │  │
│  └─────────────┘  └───────────────────┘  │
│  ┌─────────────┐  ┌───────────────────┐  │
│  │ Trim History│  │ Cache Manager     │  │
│  │ (tail/head/ │  │ (2-level prefix   │  │
│  │  smart)     │  │  segmentation)    │  │
│  └─────────────┘  └───────────────────┘  │
│  ┌─────────────┐  ┌───────────────────┐  │
│  │ RAG Engine  │  │ CLI (Rich TUI)    │  │
│  │ (LanceDB +  │  │ (info/doctor/     │  │
│  │  MiniLM)    │  │  upgrade/version) │  │
│  └─────────────┘  └───────────────────┘  │
└──────────────────────────────────────────┘
```

## How It Works

### Token Counter
Uses `tiktoken` for exact token counting. Supports `cl100k_base` (GPT-4, Claude), `o200k_base` (GPT-4o), and `p50k_base` (Codex).

### Trim History
Three strategies with **strict budget guarantee**:
- **tail**: Keep the most recent messages
- **head**: Keep the oldest messages
- **smart**: Protect system messages + recent turns, compress the middle. If anchors exceed budget, compacts into a policy digest.

### RAG Engine
Local vector search using **LanceDB** (serverless) + **paraphrase-multilingual-MiniLM-L12-v2** (multilingual embeddings).
- Automatic deduplication by file hash
- Token-budgeted retrieval with skip-and-continue packing
- Per-source chunk limits (`max_chunks_per_source`)
- Score filtering (`min_score`)

### Cache Manager
Two-level prefix segmentation for optimal cache reuse:
- **Base prefix**: system/developer instructions (stable across turns)
- **RAG prefix**: injected knowledge context (may change)
- When only RAG changes, base prefix cache is preserved
- Canonical hashing (ignores whitespace differences)
- Real tiktoken metrics

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
```

## Requirements

- Python >= 3.10
- ~500MB disk for sentence-transformers model (downloaded once on first use)
- No GPU required — runs on CPU

## License

[MIT License](LICENSE.md)
