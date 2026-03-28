# MMCP — Monster Model Context Protocol

> LLM context optimization server with local RAG, intelligent trim history, token counting, and prompt caching.
> Zero API calls — everything runs locally on your machine.

## Install

### From GitHub (recommended)

```bash
pip install git+https://github.com/ErickGuerron/contexto-life.git
```

This installs the `mmcp` CLI command globally. Verify:

```bash
mmcp --help
```

### From source (for development)

```bash
git clone https://github.com/ErickGuerron/contexto-life.git
cd contexto-life
pip install -e ".[dev]"
```

## Setup with MCP Clients

### OpenCode

Add to your `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "mmcp": {
      "type": "local",
      "command": ["mmcp"],
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
    "mmcp": {
      "command": "mmcp",
      "args": [],
      "env": {}
    }
  }
}
```

### Cursor / Windsurf

In `Settings > MCP Servers > Add Server`:

```json
{
  "mcpServers": {
    "mmcp": {
      "command": "mmcp"
    }
  }
}
```

### Gemini CLI / Antigravity

```json
{
  "mcpServers": {
    "mmcp": {
      "command": "mmcp"
    }
  }
}
```

### Running from source (without install)

If you cloned the repo and didn't do `pip install`:

```json
{
  "command": ["python", "-m", "mmcp"]
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
| Cache Context | `cache_context` | Cache-aware message processing for provider caching |
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
│              MMCP Server                 │
│  ┌─────────────┐  ┌───────────────────┐  │
│  │ Token       │  │ Trim History      │  │
│  │ Counter     │  │ (tail/head/smart) │  │
│  │ (tiktoken)  │  │                   │  │
│  └─────────────┘  └───────────────────┘  │
│  ┌─────────────┐  ┌───────────────────┐  │
│  │ RAG Engine  │  │ Cache Manager     │  │
│  │ (LanceDB + │  │ (Store + Loop +   │  │
│  │  MiniLM)    │  │  Canonical Hash)  │  │
│  └─────────────┘  └───────────────────┘  │
└──────────────────────────────────────────┘
```

## How It Works

### Token Counter
Uses `tiktoken` for exact token counting. Supports `cl100k_base` (GPT-4, Claude), `o200k_base` (GPT-4o), and `p50k_base` (Codex).

### Trim History
Three strategies to reduce message history:
- **tail**: Keep the most recent messages
- **head**: Keep the oldest messages
- **smart**: Protect system messages + recent turns, compress the middle

### RAG Engine
Local vector search using **LanceDB** (serverless) + **paraphrase-multilingual-MiniLM-L12-v2** (multilingual embeddings).
- Automatic deduplication by file hash
- Token-budgeted retrieval (`max_tokens`)
- Per-source chunk limits (`max_chunks_per_source`)
- Score filtering (`min_score`)

### Cache Manager
Detects when the static prefix (system prompt + RAG context) hasn't changed between turns, enabling provider-level prompt caching (Anthropic/Google/OpenAI save up to 90% on cached prefixes).
- Canonical prefix hashing (ignores whitespace differences)
- Real tiktoken metrics (not estimates)
- Clean messages (no internal metadata injected)

## Development

```bash
# Run with HTTP transport for testing
mmcp --transport http

# Or from source
python -m mmcp --transport http

# Run benchmarks
python benchmarks/run_context_benchmarks.py

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

MIT
