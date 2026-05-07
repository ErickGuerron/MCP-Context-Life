# Installation Guide

Complete installation instructions for Context-Life across all supported platforms and methods.

---

## Windows — Scoop (Recommended)

Scoop is the recommended installation method for Windows users. It provides:
- Automatic updates via `scoop update`
- User-level installation (no admin required)
- Clean uninstallation
- Version pinning support

### Install Scoop (if you don't have it)

Open PowerShell and run:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
irm get.scoop.sh | iex
```

For full Scoop documentation, visit [scoop.sh](https://scoop.sh).

### Install Context-Life

```bash
# Add the Context-Life bucket
scoop bucket add context-life https://github.com/ErickGuerron/MCP-Context-Life

# Install Context-Life
scoop install context-life

# Verify installation
context-life version
```

### Update Context-Life

```bash
scoop update context-life
```

### Uninstall

```bash
scoop uninstall context-life
```

### Pin a Specific Version

```bash
scoop install context-life@0.7.1
```

---

## Cross-Platform Installation

### uv (Fastest)

```bash
uv tool install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

### pipx

```bash
pipx install "git+https://github.com/ErickGuerron/MCP-Context-Life.git"
```

### pip

```bash
pip install git+https://github.com/ErickGuerron/MCP-Context-Life.git
```

### Docker

```bash
docker build -t context-life .
docker run --rm context-life version
docker run --rm context-life info
docker run --rm context-life doctor
```

---

## Install Profiles

| Profile | Command | Description |
|---------|---------|-------------|
| **Full** (default) | `uv tool install "git+..."` | Includes RAG with LanceDB + sentence-transformers |
| **Core** | `pip install "context-life[core]"` | Token counting + trim only, no ML dependencies |
| **RAG** | `pip install "context-life[rag]"` | LanceDB + sentence-transformers only |
| **Dev** | `pip install -e ".[dev]"` | Full install with dev dependencies (from source) |

---

## From Source

```bash
git clone https://github.com/ErickGuerron/MCP-Context-Life.git
cd MCP-Context-Life
pip install -e ".[dev]"
```

---

## Requirements

- Python >= 3.10
- ~500MB disk for sentence-transformers model (downloaded once on first use)
- No GPU required — runs on CPU

---

## Post-Installation

After installing, verify your setup:

```bash
context-life doctor    # Check environment and dependencies
context-life info      # Show system info and config
```

For MCP client integration, see:
- [Orchestrator Integration Guide](orchestrator-integration.md) — Setup with OpenCode, Claude Desktop, Cursor, and other MCP clients