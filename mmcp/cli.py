"""
Context-Life (CL) — CLI Module

Beautiful terminal interface using Rich for:
  - Startup banner and server info
  - `context-life upgrade` — self-update from GitHub releases (not HEAD)
  - `context-life info` — show system specs
  - `context-life doctor` — environment validation
  - `context-life version` — show version
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import urllib.request
from importlib.metadata import version as pkg_version
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

CONSOLE = Console()

GITHUB_REPO = "ErickGuerron/MCP-Context-Life"
REPO_URL = f"https://github.com/{GITHUB_REPO}.git"

BANNER = r"""
   ██████╗ ██████╗ ███╗   ██╗████████╗███████╗██╗  ██╗████████╗
  ██╔════╝██╔═══██╗████╗  ██║╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝
  ██║     ██║   ██║██╔██╗ ██║   ██║   █████╗   ╚███╔╝    ██║
  ██║     ██║   ██║██║╚██╗██║   ██║   ██╔══╝   ██╔██╗    ██║
  ╚██████╗╚██████╔╝██║ ╚████║   ██║   ███████╗██╔╝ ██╗   ██║
   ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝
                  ██╗     ██╗███████╗███████╗
                  ██║     ██║██╔════╝██╔════╝
                  ██║     ██║█████╗  █████╗
                  ██║     ██║██╔══╝  ██╔══╝
                  ███████╗██║██║     ███████╗
                  ╚══════╝╚═╝╚═╝     ╚══════╝
"""


def get_version() -> str:
    """Get installed version, falling back to __init__ if not pip-installed."""
    try:
        return pkg_version("context-life")
    except Exception:
        try:
            from mmcp import __version__
            return __version__
        except Exception:
            return "dev"


def _safe_import_check(module: str) -> tuple[bool, str]:
    """Check if a module can be imported and get its version."""
    try:
        mod = __import__(module)
        ver = getattr(mod, "__version__", getattr(mod, "VERSION", "✓"))
        return True, str(ver)
    except ImportError:
        return False, "✗ not found"


def _fetch_latest_release() -> tuple[str | None, str | None]:
    """Fetch the latest release tag from GitHub API. Returns (tag, url) or (None, None)."""
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            tag = data.get("tag_name", "").lstrip("v")
            return tag, data.get("html_url")
    except Exception:
        # Fallback: try tags endpoint
        try:
            tags_url = f"https://api.github.com/repos/{GITHUB_REPO}/tags?per_page=1"
            req = urllib.request.Request(tags_url, headers={"Accept": "application/vnd.github.v3+json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                tags = json.loads(resp.read().decode())
                if tags:
                    tag = tags[0].get("name", "").lstrip("v")
                    return tag, f"https://github.com/{GITHUB_REPO}/releases/tag/{tags[0]['name']}"
        except Exception:
            pass
    return None, None


def print_banner():
    """Print the Context-Life startup banner."""
    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    CONSOLE.print(banner_text)
    CONSOLE.print(
        f"  [bold white]Context-Life[/] [dim](CL)[/dim] [bold green]v{ver}[/]  "
        f"[dim]— LLM Context Optimization MCP Server[/dim]\n",
        justify="center",
    )


def show_info():
    """Display system info, dependencies, and configuration."""
    print_banner()

    # System info
    sys_table = Table(title="🖥  System", box=box.ROUNDED, border_style="blue", title_style="bold blue")
    sys_table.add_column("Property", style="cyan", width=22)
    sys_table.add_column("Value", style="white")
    sys_table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys_table.add_row("Platform", platform.platform())
    sys_table.add_row("Architecture", platform.machine())
    sys_table.add_row("OS", platform.system())
    CONSOLE.print(sys_table)
    CONSOLE.print()

    # Config info
    from mmcp.config import get_config, _default_config_path, _default_data_path
    cfg = get_config()
    cfg_table = Table(title="⚙️  Configuration", box=box.ROUNDED, border_style="dim", title_style="bold white")
    cfg_table.add_column("Setting", style="cyan", width=28)
    cfg_table.add_column("Value", style="white")
    cfg_table.add_row("Config file", str(_default_config_path()))
    cfg_table.add_row("Data directory", str(cfg.resolve_data_dir()))
    cfg_table.add_row("RAG DB path", cfg.resolve_rag_db_path())
    cfg_table.add_row("RAG top_k", str(cfg.rag_top_k))
    cfg_table.add_row("RAG min_score", str(cfg.rag_min_score))
    cfg_table.add_row("Token budget", f"{cfg.token_budget_default:,}")
    cfg_table.add_row("Trim preserve_recent", str(cfg.trim_preserve_recent))
    CONSOLE.print(cfg_table)
    CONSOLE.print()

    # Dependencies
    deps = [
        ("mcp", "mcp"), ("tiktoken", "tiktoken"), ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"), ("pyarrow", "pyarrow"), ("rich", "rich"),
    ]
    dep_table = Table(title="📦 Dependencies", box=box.ROUNDED, border_style="green", title_style="bold green")
    dep_table.add_column("Package", style="cyan", width=25)
    dep_table.add_column("Status", width=15)
    dep_table.add_column("Version", style="white")
    for name, importable in deps:
        ok, ver = _safe_import_check(importable)
        status = "[green]installed[/]" if ok else "[red]missing[/]"
        dep_table.add_row(name, status, ver)
    CONSOLE.print(dep_table)
    CONSOLE.print()

    # Tools
    feat_table = Table(title="⚡ Available Tools", box=box.ROUNDED, border_style="magenta", title_style="bold magenta")
    feat_table.add_column("Tool", style="cyan", width=28)
    feat_table.add_column("Description", style="white")
    for tool, desc in [
        ("count_tokens_tool", "Count tokens (tiktoken, real count)"),
        ("count_messages_tokens_tool", "Count tokens in message arrays"),
        ("optimize_messages", "Trim history (tail/head/smart)"),
        ("search_context", "Semantic RAG search"),
        ("index_knowledge", "Index files into LanceDB"),
        ("cache_context", "Cache-aware message optimization"),
        ("rag_stats", "Knowledge base statistics"),
        ("clear_knowledge", "Clear indexed knowledge"),
        ("reset_token_budget", "Reset token budget tracker"),
    ]:
        feat_table.add_row(tool, desc)
    CONSOLE.print(feat_table)
    CONSOLE.print()

    # Resources
    res_table = Table(title="📊 Resources", box=box.ROUNDED, border_style="yellow", title_style="bold yellow")
    res_table.add_column("URI", style="cyan", width=28)
    res_table.add_column("Description", style="white")
    res_table.add_row("status://token_budget", "Token budget consumption")
    res_table.add_row("cache://status", "Cache hit/miss stats")
    res_table.add_row("rag://stats", "RAG knowledge base info")
    CONSOLE.print(res_table)
    CONSOLE.print()

    # Integration panel
    CONSOLE.print(Panel(
        "[bold cyan]MCP Client Config:[/]\n\n"
        '[white]"context-life": {\n'
        '  "type": "local",\n'
        '  "command": ["context-life"],\n'
        '  "enabled": true\n'
        "}[/]",
        title="🔌 Integration", border_style="dim", box=box.ROUNDED,
    ))


def do_upgrade(target_version: str | None = None, dry_run: bool = False):
    """Self-update from GitHub releases (not HEAD)."""
    print_banner()

    old_version = get_version()

    # Resolve target version
    if target_version:
        tag = target_version.lstrip("v")
        release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/v{tag}"
    else:
        with CONSOLE.status("[bold cyan]Checking for latest release...[/]", spinner="dots"):
            tag, release_url = _fetch_latest_release()

    if not tag:
        CONSOLE.print("\n  [bold yellow]⚠ Could not fetch release info from GitHub[/]")
        CONSOLE.print("  [dim]Falling back to latest from repository...[/]\n")
        tag = None
        install_target = f"git+{REPO_URL}"
    else:
        install_target = f"git+{REPO_URL}@v{tag}"

    CONSOLE.print(Panel(
        f"[bold]Current version:[/] [yellow]v{old_version}[/]\n"
        f"[bold]Target version:[/]  [green]v{tag or 'latest'}[/]"
        + (f"\n[dim]{release_url}[/]" if release_url else ""),
        title="🔄 Context-Life Upgrade", border_style="yellow", box=box.ROUNDED,
    ))

    if tag and tag == old_version:
        CONSOLE.print(f"\n  [bold green]✓ Already up to date[/] [dim](v{old_version})[/]\n")
        return

    if dry_run:
        CONSOLE.print(f"\n  [bold cyan]ℹ Dry run:[/] would install [green]v{tag or 'latest'}[/]")
        CONSOLE.print(f"  [dim]pip install --upgrade {install_target}[/]\n")
        return

    with CONSOLE.status("[bold cyan]Downloading and installing...[/]", spinner="dots"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", install_target],
            capture_output=True, text=True,
        )

    if result.returncode == 0:
        new_version = get_version()
        if new_version != old_version:
            CONSOLE.print(f"\n  [bold green]✓ Upgraded![/] [yellow]v{old_version}[/] → [green]v{new_version}[/]\n")
        else:
            CONSOLE.print(f"\n  [bold green]✓ Already up to date[/] [dim](v{new_version})[/]\n")
        for line in result.stdout.strip().split("\n")[-5:]:
            CONSOLE.print(f"  [dim]{line}[/]")
    else:
        CONSOLE.print(f"\n  [bold red]✗ Upgrade failed[/]\n")
        CONSOLE.print(f"  [red]{result.stderr.strip()[:500]}[/]")
        sys.exit(1)


def do_doctor():
    """Run environment diagnostics."""
    print_banner()

    CONSOLE.print(Panel("[bold]Running environment checks...[/]", title="🩺 Doctor", border_style="cyan", box=box.ROUNDED))
    CONSOLE.print()

    checks: list[tuple[str, str, str]] = []  # (name, status, detail)

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", "✅" if py_ok else "❌", f"{py_ver} {'(>= 3.10 required)' if not py_ok else ''}"))

    # 2. Package version
    ver = get_version()
    checks.append(("Installed version", "✅", f"v{ver}"))

    # 3. Dependencies
    critical_deps = [
        ("mcp", "mcp"), ("tiktoken", "tiktoken"), ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"), ("pyarrow", "pyarrow"), ("rich", "rich"),
    ]
    for name, importable in critical_deps:
        ok, dep_ver = _safe_import_check(importable)
        checks.append((f"  {name}", "✅" if ok else "❌", dep_ver))

    # 4. Config file
    from mmcp.config import _default_config_path, _default_data_path, get_config
    cfg_path = _default_config_path()
    cfg_exists = cfg_path.exists()
    checks.append(("Config file", "✅" if cfg_exists else "ℹ️", f"{cfg_path}" + (" (using defaults)" if not cfg_exists else "")))

    # 5. Data directory
    cfg = get_config()
    data_dir = cfg.resolve_data_dir()
    checks.append(("Data directory", "✅", str(data_dir)))

    # 6. LanceDB path
    rag_path = Path(cfg.resolve_rag_db_path())
    rag_writable = os.access(rag_path.parent, os.W_OK) if rag_path.parent.exists() else False
    checks.append(("LanceDB path", "✅" if rag_writable else "⚠️", f"{rag_path}" + (" (not writable)" if not rag_writable else "")))

    # 7. Model cache
    model_cache = Path.home() / ".cache" / "huggingface"
    if os.name == "nt":
        model_cache = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "huggingface"
    cache_exists = model_cache.exists()
    checks.append(("Model cache", "✅" if cache_exists else "ℹ️", f"{model_cache}" + (" (will download on first use)" if not cache_exists else "")))

    # 8. Latest release
    with CONSOLE.status("[dim]Checking GitHub...[/]", spinner="dots"):
        latest_tag, _ = _fetch_latest_release()
    if latest_tag:
        is_latest = latest_tag == ver
        checks.append(("Latest release", "✅" if is_latest else "⬆️",
                       f"v{latest_tag}" + ("" if is_latest else f" (you have v{ver})")))
    else:
        checks.append(("Latest release", "⚠️", "Could not reach GitHub API"))

    # Display results
    doc_table = Table(box=box.ROUNDED, border_style="cyan", title="Diagnostic Results", title_style="bold cyan")
    doc_table.add_column("Check", style="white", width=28)
    doc_table.add_column("", width=3)
    doc_table.add_column("Detail", style="dim")

    for name, status, detail in checks:
        doc_table.add_row(name, status, detail)

    CONSOLE.print(doc_table)
    CONSOLE.print()

    has_errors = any(s == "❌" for _, s, _ in checks)
    if has_errors:
        CONSOLE.print("  [bold red]Some checks failed.[/] Fix the issues above and run again.\n")
    else:
        CONSOLE.print("  [bold green]All checks passed![/] Context-Life is ready to use.\n")


def show_version():
    """Print version string."""
    ver = get_version()
    CONSOLE.print(f"[bold cyan]context-life[/] [green]v{ver}[/]")


def show_help():
    """Print usage help."""
    print_banner()

    help_table = Table(title="📖 Commands", box=box.ROUNDED, border_style="cyan", title_style="bold cyan")
    help_table.add_column("Command", style="bold white", width=40)
    help_table.add_column("Description", style="white")

    commands = [
        ("context-life", "Start MCP server (stdio transport)"),
        ("context-life serve", "Start MCP server (stdio transport)"),
        ("context-life serve --http", "Start MCP server (HTTP transport)"),
        ("context-life info", "Show system info, config, dependencies, tools"),
        ("context-life doctor", "Run environment diagnostics"),
        ("context-life upgrade", "Upgrade to latest GitHub release"),
        ("context-life upgrade --version <tag>", "Install specific version"),
        ("context-life upgrade --dry-run", "Check upgrade without installing"),
        ("context-life version", "Show version"),
        ("context-life help", "Show this help"),
    ]
    for cmd, desc in commands:
        help_table.add_row(cmd, desc)

    CONSOLE.print(help_table)
    CONSOLE.print()
