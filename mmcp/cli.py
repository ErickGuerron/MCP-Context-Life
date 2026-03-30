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
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from rich import box
from rich.align import Align


def _ensure_utf8_output() -> bool:
    """Try to make stdout/stderr unicode-safe, especially on Windows."""
    changed = False
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
                changed = True
            except Exception:
                pass
    return changed


_ensure_utf8_output()
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
    """Check if a module is installed and get its version WITHOUT importing it.

    Uses importlib.metadata to avoid loading heavy libraries like
    sentence_transformers (which pulls in PyTorch) just for a version check.
    """
    from importlib.metadata import version as _meta_version, PackageNotFoundError

    # Map import names to pip distribution names where they differ
    _IMPORT_TO_DIST = {
        "sentence_transformers": "sentence-transformers",
    }
    dist_name = _IMPORT_TO_DIST.get(module, module)

    try:
        ver = _meta_version(dist_name)
        return True, ver
    except PackageNotFoundError:
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
    CONSOLE.print(Align.center(banner_text))
    CONSOLE.print(
        f"  [bold white]Context-Life[/] [dim](CL)[/dim] [bold green]v{ver}[/]  "
        f"[dim]— LLM Context Optimization MCP Server[/dim]\n",
        justify="center",
    )


def _build_info_content():
    """Build the system info renderables (does NOT print)."""
    from mmcp.config import get_config, _default_config_path, _default_data_path
    from rich.columns import Columns
    from rich.console import Group

    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    title_text = Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server\n", style="bold white")

    # System info
    sys_table = Table(title="🖥  System", box=box.ROUNDED, border_style="blue", title_style="bold blue")
    sys_table.add_column("Property", style="cyan", width=22)
    sys_table.add_column("Value", style="white")
    sys_table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys_table.add_row("Platform", platform.platform())
    sys_table.add_row("Architecture", platform.machine())
    sys_table.add_row("OS", platform.system())

    # Config info
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

    # Dependencies
    deps = [
        ("mcp", "mcp"),
        ("tiktoken", "tiktoken"),
        ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"),
        ("pyarrow", "pyarrow"),
        ("rich", "rich"),
    ]
    dep_table = Table(title="📦 Dependencies", box=box.ROUNDED, border_style="green", title_style="bold green")
    dep_table.add_column("Package", style="cyan", width=25)
    dep_table.add_column("Status", width=15)
    dep_table.add_column("Version", style="white")
    for name, importable in deps:
        ok, ver = _safe_import_check(importable)
        status = "[green]installed[/]" if ok else "[red]missing[/]"
        dep_table.add_row(name, status, ver)

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
        ("get_orchestration_advice", "Actionable next step for orchestrators"),
        ("rag_stats", "Knowledge base statistics"),
        ("clear_knowledge", "Clear indexed knowledge"),
        ("reset_token_budget", "Reset token budget tracker"),
    ]:
        feat_table.add_row(tool, desc)

    # Resources
    res_table = Table(title="📊 Resources", box=box.ROUNDED, border_style="yellow", title_style="bold yellow")
    res_table.add_column("URI", style="cyan", width=28)
    res_table.add_column("Description", style="white")
    res_table.add_row("status://token_budget", "Token budget consumption")
    res_table.add_row("cache://status", "Cache hit/miss stats")
    res_table.add_row("rag://stats", "RAG knowledge base info")
    res_table.add_row("status://orchestrator", "Detected orchestrator and advisor mode")
    res_table.add_row("status://orchestration", "Static orchestration contract")

    # Integration panel
    int_panel = Panel(
        "[bold cyan]MCP Client Config:[/]\n\n"
        '[white]"context-life": {\n'
        '  "type": "local",\n'
        '  "command": ["context-life"],\n'
        '  "enabled": true\n'
        "}[/]",
        title="🔌 Integration",
        border_style="dim",
        box=box.ROUNDED,
    )

    left_group = Group(sys_table, cfg_table, dep_table)
    right_group = Group(feat_table, res_table, int_panel)
    columns = Columns([left_group, right_group], expand=True, align="center")

    return Group(
        Align.center(banner_text),
        Align.center(title_text),
        columns,
    )


def show_info():
    """Display system info inside a scrollable alternate screen."""
    content = _build_info_content()
    _show_in_scrollable_screen(content, title="System Info")


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

    CONSOLE.print(
        Align.center(
            Panel(
                f"[bold]Current version:[/] [yellow]v{old_version}[/]\n"
                f"[bold]Target version:[/]  [green]v{tag or 'latest'}[/]"
                + (f"\n[dim]{release_url}[/]" if release_url else ""),
                title="🔄 Context-Life Upgrade",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
    )

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
            capture_output=True,
            text=True,
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


def _build_doctor_content():
    """Build the doctor diagnostics renderables (does NOT print)."""
    from rich.console import Group
    from mmcp.config import _default_config_path, _default_data_path, get_config

    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    title_text = Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server\n", style="bold white")

    header_panel = Panel(
        "[bold]Environment diagnostics[/]", title="🩺 Doctor", border_style="cyan", box=box.ROUNDED
    )

    checks: list[tuple[str, str, str]] = []  # (name, status, detail)

    # 1. Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", "✅" if py_ok else "❌", f"{py_ver} {'(>= 3.10 required)' if not py_ok else ''}"))

    # 2. Package version
    checks.append(("Installed version", "✅", f"v{ver}"))

    # 3. Dependencies
    critical_deps = [
        ("mcp", "mcp"),
        ("tiktoken", "tiktoken"),
        ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"),
        ("pyarrow", "pyarrow"),
        ("rich", "rich"),
    ]
    for name, importable in critical_deps:
        ok, dep_ver = _safe_import_check(importable)
        checks.append((f"  {name}", "✅" if ok else "❌", dep_ver))

    # 4. Config file
    cfg_path = _default_config_path()
    cfg_exists = cfg_path.exists()
    checks.append(
        ("Config file", "✅" if cfg_exists else "ℹ️", f"{cfg_path}" + (" (using defaults)" if not cfg_exists else ""))
    )

    # 5. Data directory
    cfg = get_config()
    data_dir = cfg.resolve_data_dir()
    checks.append(("Data directory", "✅", str(data_dir)))

    # 6. LanceDB path
    rag_path = Path(cfg.resolve_rag_db_path())
    rag_writable = os.access(rag_path.parent, os.W_OK) if rag_path.parent.exists() else False
    checks.append(
        ("LanceDB path", "✅" if rag_writable else "⚠️", f"{rag_path}" + (" (not writable)" if not rag_writable else ""))
    )

    # 7. Model cache
    model_cache = Path.home() / ".cache" / "huggingface"
    if os.name == "nt":
        model_cache = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "huggingface"
    cache_exists = model_cache.exists()
    checks.append(
        (
            "Model cache",
            "✅" if cache_exists else "ℹ️",
            f"{model_cache}" + (" (will download on first use)" if not cache_exists else ""),
        )
    )

    # 8. Latest release (fetched before entering scrollable screen)
    try:
        latest_tag, _ = _fetch_latest_release()
    except Exception:
        latest_tag = None

    if latest_tag:
        is_latest = latest_tag == ver
        checks.append(
            (
                "Latest release",
                "✅" if is_latest else "⬆️",
                f"v{latest_tag}" + ("" if is_latest else f" (you have v{ver})"),
            )
        )
    else:
        checks.append(("Latest release", "⚠️", "Could not reach GitHub API"))

    # Display results
    doc_table = Table(box=box.ROUNDED, border_style="cyan", title="Diagnostic Results", title_style="bold cyan")
    doc_table.add_column("Check", style="white", width=28)
    doc_table.add_column("", width=3)
    doc_table.add_column("Detail", style="dim")

    for name, status, detail in checks:
        doc_table.add_row(name, status, detail)

    has_errors = any(s == "❌" for _, s, _ in checks)
    if has_errors:
        result_text = Text("  Some checks failed. Fix the issues above and run again.\n", style="bold red")
    else:
        result_text = Text("  All checks passed! Context-Life is ready to use.\n", style="bold green")

    return Group(
        Align.center(banner_text),
        Align.center(title_text),
        Align.center(header_panel),
        Text(""),
        Align.center(doc_table),
        Text(""),
        result_text,
    )


def do_doctor():
    """Run environment diagnostics inside a scrollable alternate screen."""
    content = _build_doctor_content()
    _show_in_scrollable_screen(content, title="Diagnostics")


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

    CONSOLE.print(Align.center(help_table))
    CONSOLE.print()


def format_big_number(n: int | float) -> str:
    """Format large numbers with K, M, B suffixes."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f}B"
    elif n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    elif n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(int(n))


def _build_telemetry_content():
    """Build the telemetry dashboard renderables (does NOT print)."""
    from mmcp.session_store import SessionStore
    from mmcp.config import get_config
    from rich.columns import Columns
    from rich.console import Group

    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    title_text = Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server\n", style="bold white")

    cfg = get_config()
    store = SessionStore(cfg.resolve_cache_db_path())

    weekly = store.get_weekly_usage()
    all_time = store.get_all_time_stats()

    # 1. All-Time Stats
    total_processed = all_time["used"] + all_time["saved"]
    savings_pct = (all_time["saved"] / total_processed * 100) if total_processed > 0 else 0.0

    stats_table = Table(title="💰 All-Time Savings", box=box.ROUNDED, border_style="green", title_style="bold green")
    stats_table.add_column("Metric", style="cyan", width=30)
    stats_table.add_column("Value", style="bold white", justify="right")

    stats_table.add_row("Total Processed (Sent + Hits)", format_big_number(total_processed))
    stats_table.add_row("Total Saved (Cache Hits)", f"[green]{format_big_number(all_time['saved'])}[/]")
    stats_table.add_row("Real Savings Rate", f"[bold green]{savings_pct:.1f}%[/]")

    # 2. Weekly Usage per Model
    budget = cfg.token_budget_default
    usage_table = Table(
        title="📅 Weekly Usage Tracker (7 Days)", box=box.ROUNDED, border_style="blue", title_style="bold blue"
    )
    usage_table.add_column("Model", style="cyan", width=25)
    usage_table.add_column("Budget", style="dim", justify="right")
    usage_table.add_column("Used", justify="right")
    usage_table.add_column("Remaining", justify="right")
    usage_table.add_column("Status", justify="center")

    if not weekly:
        usage_table.add_row("[dim]No usage data[/]", "-", "-", "-", "-")
    else:
        for model_name, data in weekly.items():
            used = data["used"]
            remaining = max(0, budget - used)

            # Determine status color
            if remaining < (budget * 0.15):  # Less than 15%
                color = "red"
                status = "[bold red]CRITICAL[/]"
            elif remaining < (budget * 0.30):  # Less than 30%
                color = "yellow"
                status = "[bold yellow]WARNING[/]"
            else:
                color = "green"
                status = "[bold green]OK[/]"

            usage_table.add_row(
                model_name,
                format_big_number(budget),
                f"[{color}]{format_big_number(used)}[/]",
                f"[{color}]{format_big_number(remaining)}[/]",
                status,
            )

    note_panel = Panel(
        "[dim]Note: Weekly stats reset dynamically on a rolling 7-day window.\n"
        "Budget constraints apply per distinct model string.[/]",
        border_style="dim",
        box=box.ROUNDED,
    )

    columns = Columns([stats_table, usage_table], expand=True, align="center")

    return Group(
        Align.center(banner_text),
        Align.center(title_text),
        columns,
        Text("\n"),
        Align.center(note_panel),
    )


def show_telemetry_dashboard():
    """Display the telemetry dashboard inside a scrollable alternate screen."""
    content = _build_telemetry_content()
    _show_in_scrollable_screen(content, title="Telemetry Dashboard")


def _show_in_scrollable_screen(renderable, title: str = "View"):
    """
    Display a Rich renderable inside an alternate screen buffer with
    keyboard-controlled vertical scrolling.

    Uses direct ANSI terminal writes instead of Rich Live for
    zero-overhead, buttery smooth scrolling (like less/vim).
    """
    import os
    import sys
    from io import StringIO
    from rich.console import Console as _Console

    # Step 1: Pre-render content to ANSI lines (one-time cost)
    term_width = CONSOLE.width or 120
    term_height = CONSOLE.height or 40
    viewport_height = term_height - 1  # Reserve 1 line for footer

    buf = StringIO()
    temp_console = _Console(file=buf, width=term_width, force_terminal=True)
    temp_console.print(renderable)
    content_lines = buf.getvalue().split("\n")

    # Strip trailing empty lines — Rich adds them and they inflate the
    # line count, breaking vertical centering calculations.
    while content_lines and content_lines[-1].strip() == "":
        content_lines.pop()

    # Step 2: Direct terminal I/O helpers
    write = sys.stdout.write
    flush = sys.stdout.flush

    # ANSI escape sequences
    ENTER_ALT_SCREEN = "\033[?1049h"
    EXIT_ALT_SCREEN = "\033[?1049l"
    CURSOR_HOME = "\033[H"
    CLEAR_LINE = "\033[2K"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"

    scroll_offset = 0
    max_offset = max(0, len(content_lines) - viewport_height)

    def _strip_ansi_len(s: str) -> int:
        """Estimate visible length by stripping ANSI escape sequences."""
        import re
        return len(re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", s))

    def paint():
        """Write the visible slice directly to the alternate screen."""
        nonlocal scroll_offset
        scroll_offset = max(0, min(scroll_offset, max_offset))

        total_content = len(content_lines)

        # Vertical centering: if content fits in viewport, add top padding
        if total_content <= viewport_height:
            top_pad = (viewport_height - total_content) // 2
        else:
            top_pad = 0

        # Paint each row at an explicit cursor position
        for row_idx in range(viewport_height):
            write(f"\033[{row_idx + 1};1H\033[2K")
            content_row = row_idx - top_pad
            line_idx = scroll_offset + content_row
            if 0 <= content_row and 0 <= line_idx < total_content:
                line = content_lines[line_idx]
                if _strip_ansi_len(line) > term_width:
                    line = line[:term_width + 40]
                write(line)

        # Footer on the last row of the terminal
        pos_pct = int((scroll_offset / max(1, max_offset)) * 100) if max_offset > 0 else 100
        if max_offset > 0:
            footer = f"  ↑/↓/j/k scroll · PgUp/PgDn jump · {pos_pct}%  |  ESC/b/q → back"
        else:
            footer = "  All content visible  |  ESC/b/q → back"

        write(f"\033[{term_height};1H\033[2K\033[2;3m{footer.center(term_width)}\033[0m")
        flush()

    def get_char() -> str:
        """Cross-platform blocking keypress reader."""
        try:
            if os.name == "nt":
                import msvcrt
                char = msvcrt.getch()
                if char in (b"\xe0", b"\x00"):
                    char = msvcrt.getch()
                    if char == b"H":
                        return "up"
                    if char == b"P":
                        return "down"
                    if char == b"I":
                        return "pgup"
                    if char == b"Q":
                        return "pgdn"
                    return ""
                return char.decode("utf-8").lower()
            else:
                import tty, termios
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    char = sys.stdin.read(1)
                    if char == "\x1b":
                        next1 = sys.stdin.read(1)
                        if next1 != "[":
                            return "\x1b"
                        next2 = sys.stdin.read(1)
                        if next2 == "A":
                            return "up"
                        if next2 == "B":
                            return "down"
                        if next2 == "5":
                            sys.stdin.read(1)
                            return "pgup"
                        if next2 == "6":
                            sys.stdin.read(1)
                            return "pgdn"
                    return char.lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            return ""

    # Step 3: Enter alternate screen, paint, handle input, exit
    try:
        write(ENTER_ALT_SCREEN + HIDE_CURSOR)
        flush()
        paint()

        while True:
            c = get_char()
            if c in ("\x1b", "b", "q"):
                break

            prev_offset = scroll_offset
            if c in ("j", "down"):
                scroll_offset += 1
            elif c in ("k", "up"):
                scroll_offset -= 1
            elif c == "pgdn":
                scroll_offset += viewport_height - 2
            elif c == "pgup":
                scroll_offset -= viewport_height - 2

            # Clamp BEFORE comparing — avoids repaint if already at boundary
            scroll_offset = max(0, min(scroll_offset, max_offset))
            if scroll_offset != prev_offset:
                paint()
    finally:
        write(SHOW_CURSOR + EXIT_ALT_SCREEN)
        flush()


def do_tui():
    """Starts the static interactive CLI menu using Rich Live."""
    import os
    import sys
    from rich.live import Live
    from rich.console import Group

    options = [
        ("[i] System Info", show_info),
        ("[+] Diagnostics Doctor", do_doctor),
        ("[~] Telemetry Dashboard", show_telemetry_dashboard),
        ("[*] Upgrade Context-Life", do_upgrade),
        ("[x] Exit", None),
    ]

    # We use a mutable list trick so nested functions can modify it
    # without running into 'nonlocal' scoping issues in Python 3.10
    state = {"selected": 0, "running": True, "latest_version": None}

    def check_update_bg():
        try:
            latest, _ = _fetch_latest_release()
            current = get_version()
            if latest and latest != current and latest != "dev" and current != "dev":
                state["latest_version"] = latest
        except Exception:
            pass

    import threading

    threading.Thread(target=check_update_bg, daemon=True).start()

    def get_char() -> str:
        """Cross-platform blocking keypress reader."""
        try:
            if os.name == "nt":
                import msvcrt

                char = msvcrt.getch()
                if char in (b"\xe0", b"\x00"):
                    char = msvcrt.getch()
                    if char == b"H":
                        return "up"
                    if char == b"P":
                        return "down"
                    return ""
                return char.decode("utf-8").lower()
            else:
                import tty, termios

                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    char = sys.stdin.read(1)
                    if char == "\x1b":
                        next1 = sys.stdin.read(1)
                        next2 = sys.stdin.read(1)
                        if next1 == "[":
                            if next2 == "A":
                                return "up"
                            if next2 == "B":
                                return "down"
                    return char.lower()
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            return ""

    def generate_menu():
        lines = []
        # Add a bit of top padding inside the panel
        lines.append(Text(""))

        for i, (label, _) in enumerate(options):
            if i == state["selected"]:
                lines.append(Align.center(Text(f"▶ {label}", style="bold cyan")))
            else:
                lines.append(Align.center(Text(f"  {label}", style="dim")))

        # Footer
        lines.append(Text("\n"))
        lines.append(Align.center(Text("j/k or ↑/↓ navigate • enter select • q quit", style="dim italic")))

        menu_panel = Panel(Group(*lines), title="● Main Menu", border_style="magenta", box=box.ROUNDED, width=65)

        ver = get_version()
        banner_text = Text(BANNER, style="bold cyan")

        update_alert = Text("")
        if state["latest_version"]:
            update_alert = Text(
                f"  ⚠️ NEW VERSION AVAILABLE: v{state['latest_version']}! Select [*] Upgrade Context-Life to install ⚠️  \n",
                style="bold yellow",
            )

        group = Group(
            Align.center(banner_text),
            Align.center(
                Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server\n", style="bold white")
            ),
            Align.center(update_alert),
            Align.center(menu_panel),
        )
        return group

    with Live(generate_menu(), refresh_per_second=10, screen=True, transient=True) as live:
        while state["running"]:
            c = get_char()
            if c in ("j", "down"):
                state["selected"] = (state["selected"] + 1) % len(options)
            elif c in ("k", "up"):
                state["selected"] = (state["selected"] - 1) % len(options)
            elif c in ("\r", "\n"):
                state["running"] = False
            elif c == "q":
                state["selected"] = len(options) - 1
                state["running"] = False

            live.update(generate_menu())

    # Screen closes automatically due to 'transient=True' and 'screen=True'
    action = options[state["selected"]][1]

    if action is None:
        CONSOLE.print("\n  [bold green]👋 See you next time![/]\n")
        sys.exit(0)
    else:
        # Scrollable actions (System Info, Telemetry) handle their own
        # alternate screen internally. Non-scrollable actions (Doctor,
        # Upgrade) print to terminal normally and wait for keypress.
        action()

        # After returning from a scrollable screen or normal action,
        # re-launch the main menu
        do_tui()

