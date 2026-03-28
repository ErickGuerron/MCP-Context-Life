"""
Context-Life (CL) — CLI Module

Beautiful terminal interface using Rich for:
  - Startup banner and server info
  - `context-life upgrade` — self-update from GitHub
  - `context-life info` — show system specs
  - `context-life version` — show version
"""

from __future__ import annotations

import platform
import subprocess
import sys
from importlib.metadata import version as pkg_version

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

CONSOLE = Console()

REPO_URL = "https://github.com/ErickGuerron/MCP-Context-Life.git"

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

    # System info table
    sys_table = Table(
        title="🖥  System", box=box.ROUNDED, border_style="blue",
        title_style="bold blue",
    )
    sys_table.add_column("Property", style="cyan", width=22)
    sys_table.add_column("Value", style="white")

    sys_table.add_row("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys_table.add_row("Platform", platform.platform())
    sys_table.add_row("Architecture", platform.machine())
    sys_table.add_row("OS", platform.system())

    CONSOLE.print(sys_table)
    CONSOLE.print()

    # Dependencies table
    deps = [
        ("mcp", "mcp"),
        ("tiktoken", "tiktoken"),
        ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"),
        ("pyarrow", "pyarrow"),
        ("rich", "rich"),
    ]

    dep_table = Table(
        title="📦 Dependencies", box=box.ROUNDED, border_style="green",
        title_style="bold green",
    )
    dep_table.add_column("Package", style="cyan", width=25)
    dep_table.add_column("Status", width=15)
    dep_table.add_column("Version", style="white")

    for name, importable in deps:
        ok, ver = _safe_import_check(importable)
        status = "[green]installed[/]" if ok else "[red]missing[/]"
        dep_table.add_row(name, status, ver)

    CONSOLE.print(dep_table)
    CONSOLE.print()

    # Features table
    feat_table = Table(
        title="⚡ Available Tools", box=box.ROUNDED, border_style="magenta",
        title_style="bold magenta",
    )
    feat_table.add_column("Tool", style="cyan", width=28)
    feat_table.add_column("Description", style="white")

    tools = [
        ("count_tokens_tool", "Count tokens (tiktoken, real count)"),
        ("count_messages_tokens_tool", "Count tokens in message arrays"),
        ("optimize_messages", "Trim history (tail/head/smart)"),
        ("search_context", "Semantic RAG search"),
        ("index_knowledge", "Index files into LanceDB"),
        ("cache_context", "Cache-aware message optimization"),
        ("rag_stats", "Knowledge base statistics"),
        ("clear_knowledge", "Clear indexed knowledge"),
        ("reset_token_budget", "Reset token budget tracker"),
    ]
    for tool, desc in tools:
        feat_table.add_row(tool, desc)

    CONSOLE.print(feat_table)
    CONSOLE.print()

    # Resources
    res_table = Table(
        title="📊 Resources", box=box.ROUNDED, border_style="yellow",
        title_style="bold yellow",
    )
    res_table.add_column("URI", style="cyan", width=28)
    res_table.add_column("Description", style="white")

    res_table.add_row("status://token_budget", "Token budget consumption")
    res_table.add_row("cache://status", "Cache hit/miss stats")
    res_table.add_row("rag://stats", "RAG knowledge base info")

    CONSOLE.print(res_table)
    CONSOLE.print()

    # Install instructions
    install_panel = Panel(
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
    CONSOLE.print(install_panel)


def do_upgrade():
    """Self-update from GitHub."""
    print_banner()

    CONSOLE.print(
        Panel(
            f"[bold]Upgrading from:[/] [cyan]{REPO_URL}[/]",
            title="🔄 Context-Life Upgrade",
            border_style="yellow",
            box=box.ROUNDED,
        )
    )

    old_version = get_version()
    CONSOLE.print(f"  [dim]Current version:[/] [yellow]v{old_version}[/]")
    CONSOLE.print()

    with CONSOLE.status("[bold cyan]Downloading and installing latest version...[/]", spinner="dots"):
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", f"git+{REPO_URL}"],
            capture_output=True,
            text=True,
        )

    if result.returncode == 0:
        new_version = get_version()
        if new_version != old_version:
            CONSOLE.print(
                f"\n  [bold green]✓ Upgraded![/] [yellow]v{old_version}[/] → [green]v{new_version}[/]\n"
            )
        else:
            CONSOLE.print(
                f"\n  [bold green]✓ Already up to date[/] [dim](v{new_version})[/]\n"
            )

        # Show pip output summary
        output_lines = result.stdout.strip().split("\n")
        for line in output_lines[-5:]:
            CONSOLE.print(f"  [dim]{line}[/]")
    else:
        CONSOLE.print(f"\n  [bold red]✗ Upgrade failed[/]\n")
        CONSOLE.print(f"  [red]{result.stderr.strip()}[/]")
        sys.exit(1)


def show_version():
    """Print version string."""
    ver = get_version()
    CONSOLE.print(f"[bold cyan]context-life[/] [green]v{ver}[/]")


def show_help():
    """Print usage help."""
    print_banner()

    help_table = Table(
        title="📖 Commands", box=box.ROUNDED, border_style="cyan",
        title_style="bold cyan",
    )
    help_table.add_column("Command", style="bold white", width=32)
    help_table.add_column("Description", style="white")

    commands = [
        ("context-life", "Start MCP server (stdio transport)"),
        ("context-life serve", "Start MCP server (stdio transport)"),
        ("context-life serve --http", "Start MCP server (HTTP transport)"),
        ("context-life info", "Show system info, dependencies, tools"),
        ("context-life upgrade", "Self-update from GitHub"),
        ("context-life version", "Show version"),
        ("context-life help", "Show this help"),
    ]
    for cmd, desc in commands:
        help_table.add_row(cmd, desc)

    CONSOLE.print(help_table)
    CONSOLE.print()
