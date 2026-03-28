# Context-Life (CL) — LLM Context Optimization MCP Server

> MCP server for LLM context optimization with local RAG, intelligent trim history, token counting, and prompt caching.
> Zero API calls — everything runs locally on your machine.

## Install

### From GitHub (recommended)

```bash
pip install git+https://github.com/ErickGuerron/MCP-Context-Life.git
```

This installs the `context-life` CLI command globally. Verify:

```bash
context-life --help
```

### From source (for development)

```bash
git clone https://github.com/ErickGuerron/MCP-Context-Life.git
cd MCP-Context-Life
pip install -e ".[dev]"
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

### Cursor / Windsurf

```json
{
  "mcpServers": {
    "context-life": {
      "command": "context-life"
    }
  }
}
```

### Gemini CLI / Antigravity

```json
{
  "mcpServers": {
    "context-life": {
      "command": "context-life"
    }
  }
}
```

### Running from source (without install)

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
│           Context-Life Server            │
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
context-life --transport http

# Or from source
python -m mmcp --transport http

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
