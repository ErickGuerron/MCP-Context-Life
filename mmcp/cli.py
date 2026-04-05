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
from dataclasses import dataclass
from io import StringIO
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Callable

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


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


@dataclass(slots=True)
class MenuItem:
    """Single selectable menu item."""

    label: str
    description: str = ""
    action: Callable[[], object] | None = None
    submenu: MenuScreen | None = None
    inline_value: Callable[[], str] | None = None


@dataclass(slots=True)
class MenuScreen:
    """Stateful menu screen rendered in the TUI."""

    title: str
    subtitle: str
    items: list[MenuItem]
    help_text: str = "j/k: navigate • enter: select • esc: back • q: quit"
    selected: int = 0
    empty_message: str = "No items available."


@dataclass(slots=True)
class MenuActionResult:
    """Side effects requested by a menu action after it completes."""

    back_levels: int = 0


def _title_case_mode(mode: str) -> str:
    """Format config modes for inline menu labels."""
    return mode.strip().title()


def _current_warmup_mode_label() -> str:
    """Read the current persisted warmup mode for inline config labels."""
    from mmcp.config import get_config

    return _title_case_mode(get_config().rag_warmup_mode)


def _render_renderable_to_lines(renderable, width: int) -> list[str]:
    """Pre-render a Rich renderable into ANSI-safe lines."""
    temp_buffer = StringIO()
    temp_console = Console(file=temp_buffer, width=width, force_terminal=True)
    temp_console.print(renderable)
    lines = temp_buffer.getvalue().split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def _menu_item_display_label(item: MenuItem) -> str:
    """Resolve the runtime label shown for a menu item."""
    if item.inline_value is None:
        return item.label
    return f"{item.label}: {item.inline_value()}"


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
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _meta_version

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


def _build_rag_warmup_table():
    """Build a table explaining persistent RAG warmup modes and MCP impact."""
    from mmcp.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    table = Table(title="🔥 RAG Warmup Modes", box=box.ROUNDED, border_style="red", title_style="bold red")
    table.add_column("Mode", style="cyan", width=18)
    table.add_column("MCP startup", style="white", width=28)
    table.add_column("First RAG search/index", style="white", width=34)
    table.add_column("Resources", style="white", width=28)

    for mode in ("lazy", "startup", "manual"):
        info = details["modes"][mode]
        label = info["label"]
        if mode == details["current_mode"]:
            label = f"[bold green]{label}[/]"
        table.add_row(label, info["startup_impact"], info["first_use_impact"], info["resource_impact"])

    return table


def _build_rag_warmup_summary_panel():
    """Current warmup mode summary panel."""
    from mmcp.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    current = details["current"]
    return Panel(
        f"[bold]Current mode:[/] [green]{details['current_mode']}[/]\n"
        f"[bold]MCP impact:[/] {current['mcp_impact']}\n"
        f"[bold]Startup:[/] {current['startup_impact']}\n"
        f"[bold]First RAG use:[/] {current['first_use_impact']}\n"
        f"[bold]Resources:[/] {current['resource_impact']}\n\n"
        "[dim]Persist it with `context-life warmup set <lazy|startup|manual>` or trigger `context-life prewarm`.[/]",
        title="⚙️ RAG Warmup Status",
        border_style="red",
        box=box.ROUNDED,
    )


def _build_rag_warmup_interactive_actions_panel():
    """Reference panel for the stateful warmup selector."""
    actions = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan")
    actions.add_column("Key", style="bold white", width=18)
    actions.add_column("Behavior", style="white", width=74)
    actions.add_row("j / ↓", "Move to the next option.")
    actions.add_row("k / ↑", "Move to the previous option.")
    actions.add_row("enter", "Open a section or execute the selected action.")
    actions.add_row("esc", "Go back to the previous menu.")
    actions.add_row("q", "Quit the interactive menu.")

    return Panel(
        actions,
        title="🎛️ Interactive Warmup Selector",
        subtitle="Stateful menu navigation with the same keys used across the TUI.",
        border_style="cyan",
        box=box.ROUNDED,
    )


def _render_rag_warmup_interactive_selector():
    """Build the interactive selector screen renderable."""
    return Group(
        _build_rag_warmup_summary_panel(),
        Text(""),
        _build_rag_warmup_table(),
        Text(""),
        _build_rag_warmup_interactive_actions_panel(),
    )


def _read_tui_key() -> str:
    """Cross-platform blocking key reader for stateful menu navigation."""
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
            if char == b"\r":
                return "enter"
            if char == b"\x1b":
                return "esc"
            return char.decode("utf-8", errors="ignore").lower()

        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
            if char in ("\r", "\n"):
                return "enter"
            if char == "\x1b":
                next1 = sys.stdin.read(1)
                if next1 != "[":
                    return "esc"
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
                return ""
            return char.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        return ""


def _clamp_menu_selection(screen: MenuScreen):
    """Keep menu selection inside current item bounds."""
    if not screen.items:
        screen.selected = 0
        return
    screen.selected = max(0, min(screen.selected, len(screen.items) - 1))


def _move_menu_selection(screen: MenuScreen, delta: int):
    """Move current selection within menu bounds."""
    if not screen.items:
        screen.selected = 0
        return
    screen.selected = max(0, min(screen.selected + delta, len(screen.items) - 1))


def _build_tui_header(path: str, subtitle: str, latest_version: str | None = None):
    """Render shared TUI header panels."""
    header = Panel(
        f"[bold white]{path}[/]\n[dim]{subtitle}[/]",
        title="Context-Life",
        border_style="magenta",
        box=box.ROUNDED,
    )

    if not latest_version:
        return header

    return Group(
        header,
        Text(""),
        Panel(
            f"[bold yellow]New version available:[/] v{latest_version}\n"
            "[dim]Open Config → Upgrade Context-Life to install it.[/]",
            title="Update",
            border_style="yellow",
            box=box.ROUNDED,
        ),
    )


def _build_menu_panel(screen: MenuScreen, path: str, latest_version: str | None = None):
    """Build the full stateful menu renderable."""
    _clamp_menu_selection(screen)

    rows: list[object] = []
    if screen.items:
        for index, item in enumerate(screen.items):
            is_active = index == screen.selected
            pointer = "▶" if is_active else " "
            style = "bold black on cyan" if is_active else "white"
            label = f"{pointer} {_menu_item_display_label(item)}"
            if item.submenu is not None:
                label = f"{label}  ›"
            rows.append(Text(label, style=style))
            if item.description:
                desc_style = "cyan" if is_active else "dim"
                rows.append(Text(f"    {item.description}", style=desc_style))
            rows.append(Text(""))
    else:
        rows.append(Text(screen.empty_message, style="dim"))
        rows.append(Text(""))

    body = Panel(
        Group(*rows),
        title=screen.title,
        subtitle="Use enter to select",
        border_style="cyan",
        box=box.ROUNDED,
        width=84,
    )

    footer = Panel(screen.help_text, border_style="dim", box=box.ROUNDED)

    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    title_text = Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server", style="bold white")

    return Group(
        Align.center(banner_text),
        Align.center(title_text),
        Text(""),
        Align.center(_build_tui_header(path, screen.subtitle, latest_version)),
        Text(""),
        Align.center(body),
        Text(""),
        Align.center(footer),
    )


def _run_menu_action(
    action: Callable[[], None],
    write,
    flush,
    show_cursor: str,
    exit_alt_screen: str,
    enter_alt_screen: str,
    hide_cursor: str,
) -> MenuActionResult | None:
    """Temporarily leave the menu screen, run an action, then return."""
    write(show_cursor + exit_alt_screen)
    flush()
    try:
        return action()
    finally:
        write(enter_alt_screen + hide_cursor)
        flush()


def _show_stateful_menu(root_screen: MenuScreen):
    """Render a full-screen stateful menu with nested navigation."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit("Interactive TUI requires a TTY. Use direct commands like `context-life info` instead.")

    stack = [root_screen]
    state = {"latest_version": None}

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

    write = sys.stdout.write
    flush = sys.stdout.flush
    enter_alt_screen = "\033[?1049h"
    exit_alt_screen = "\033[?1049l"
    hide_cursor = "\033[?25l"
    show_cursor = "\033[?25h"
    clear_screen = "\033[2J\033[H"

    def paint():
        current = stack[-1]
        path = "  ›  ".join(menu.title for menu in stack)
        renderable = _build_menu_panel(current, path, state["latest_version"])
        term_width = CONSOLE.width or 120
        term_height = CONSOLE.height or 40
        lines = _render_renderable_to_lines(renderable, term_width)

        write(clear_screen)
        for row_idx in range(term_height):
            write(f"\033[{row_idx + 1};1H\033[2K")
            if row_idx < len(lines):
                write(lines[row_idx])
        flush()

    try:
        write(enter_alt_screen + hide_cursor)
        flush()
        paint()

        while stack:
            current = stack[-1]
            key = _read_tui_key()

            if key in ("j", "down"):
                _move_menu_selection(current, 1)
                paint()
                continue
            if key in ("k", "up"):
                _move_menu_selection(current, -1)
                paint()
                continue
            if key == "q":
                break
            if key == "esc":
                if len(stack) == 1:
                    break
                stack.pop()
                paint()
                continue
            if key != "enter" or not current.items:
                continue

            item = current.items[current.selected]
            if item.submenu is not None:
                _clamp_menu_selection(item.submenu)
                stack.append(item.submenu)
                paint()
                continue

            if item.action is not None:
                result = _run_menu_action(
                    item.action, write, flush, show_cursor, exit_alt_screen, enter_alt_screen, hide_cursor
                )
                if result is not None:
                    for _ in range(min(result.back_levels, max(0, len(stack) - 1))):
                        stack.pop()
                paint()
    finally:
        write(show_cursor + exit_alt_screen)
        flush()


def show_rag_warmup_info():
    """Display RAG warmup mode details."""
    _show_in_scrollable_screen(
        Group(_build_rag_warmup_summary_panel(), Text(""), _build_rag_warmup_table()), title="RAG Warmup"
    )


def set_rag_warmup_mode(mode: str) -> str:
    """Persist a new RAG warmup mode."""
    from mmcp.config import VALID_RAG_WARMUP_MODES, get_config, normalize_rag_warmup_mode, save_config

    normalized = normalize_rag_warmup_mode(mode)
    if normalized != mode.strip().lower() or normalized not in VALID_RAG_WARMUP_MODES:
        raise ValueError(f"Invalid warmup mode: {mode}. Use lazy, startup, or manual.")

    cfg = get_config()
    cfg.rag_warmup_mode = normalized
    path = save_config(cfg)
    return str(path)


def _show_saved_warmup_mode(mode: str):
    """Persist a warmup mode and show the result."""
    from mmcp.config import get_config

    current_mode = get_config().rag_warmup_mode
    path = set_rag_warmup_mode(mode)

    if current_mode == mode:
        message = f"[bold]Warmup mode:[/] [green]{mode}[/]\n[dim]Already active. Config remains at {path}[/]"
    else:
        message = f"[bold]Warmup mode updated:[/] [yellow]{current_mode}[/] → [green]{mode}[/]\n[dim]Saved in {path}[/]"

    CONSOLE.print(Panel(message, title="⚙️ Warmup Updated", border_style="green", box=box.ROUNDED))


def _set_warmup_mode_and_return(mode: str) -> MenuActionResult:
    """Persist the warmup mode and return to Config."""
    _show_saved_warmup_mode(mode)
    return MenuActionResult(back_levels=1)


def _build_warmup_menu() -> MenuScreen:
    """Warmup submenu integrated into the stateful TUI."""
    return MenuScreen(
        title="Config / Warmup",
        subtitle="Inspect and configure RAG warmup without leaving the navigable menu flow.",
        items=[
            MenuItem(
                "Show warmup status", "See current mode, startup impact, and mode comparison.", show_rag_warmup_info
            ),
            MenuItem(
                "Set Lazy",
                "Fast startup; first RAG action pays the warmup cost.",
                lambda: _set_warmup_mode_and_return("lazy"),
            ),
            MenuItem(
                "Set Startup",
                "Load the embedding model during MCP startup for fastest first RAG use.",
                lambda: _set_warmup_mode_and_return("startup"),
            ),
            MenuItem(
                "Set Manual",
                "Keep full control and prewarm explicitly only when you decide.",
                lambda: _set_warmup_mode_and_return("manual"),
            ),
            MenuItem("Prewarm now", "Load the model immediately without changing the saved mode.", prewarm_rag_now_cli),
        ],
    )


def _build_config_menu() -> MenuScreen:
    """First-level configuration section."""
    return MenuScreen(
        title="Config",
        subtitle="Configuration actions, persistent settings, and operational controls.",
        items=[
            MenuItem(
                "RAG Warmup",
                "Open the integrated warmup selector and status screens.",
                submenu=_build_warmup_menu(),
                inline_value=_current_warmup_mode_label,
            ),
            MenuItem("Upgrade Context-Life", "Install the latest GitHub release when you are ready.", do_upgrade),
        ],
    )


def _build_metrics_menu() -> MenuScreen:
    """First-level diagnostics and metrics section."""
    return MenuScreen(
        title="Metrics",
        subtitle="Status, diagnostics, and runtime visibility for the current environment.",
        items=[
            MenuItem("Info", "System, config, dependencies, tools, and resources overview.", show_info),
            MenuItem("Health", "Environment diagnostics and readiness checks.", do_doctor),
            MenuItem("Telemetry", "Weekly usage, savings, and budget tracking dashboard.", show_telemetry_dashboard),
        ],
    )


def _build_main_tui_menu() -> MenuScreen:
    """Top-level stateful TUI menu."""
    return MenuScreen(
        title="Main Menu",
        subtitle="Pick a section, move with j/k or arrows, and stay inside one consistent menu architecture.",
        items=[
            MenuItem("Config", "Warmup settings and configurable operational actions.", submenu=_build_config_menu()),
            MenuItem("Metrics", "Info, health, telemetry, and diagnostic resources.", submenu=_build_metrics_menu()),
        ],
        help_text="j/k: navigate • enter: select • esc: back • q: quit",
    )


def prewarm_rag_now_cli():
    """Explicit CLI action to prewarm the RAG model immediately."""
    from mmcp.server import prewarm_rag_now

    result = prewarm_rag_now()
    CONSOLE.print(
        Panel(
            f"[bold]Mode:[/] [green]{result['mode']}[/]\n"
            f"[bold]Already loaded:[/] {'yes' if result['already_loaded'] else 'no'}\n"
            f"[bold]Model loaded:[/] {'yes' if result['model_loaded'] else 'no'}\n\n"
            f"{result['message']}",
            title="🔥 Prewarm RAG Now",
            border_style="green",
            box=box.ROUNDED,
        )
    )


def run_rag_warmup_interactive(input_fn=None):
    """Open the warmup submenu using the shared stateful menu architecture."""
    _show_stateful_menu(_build_warmup_menu())


def do_rag_warmup_command(args: list[str]):
    """Handle `context-life warmup ...` subcommands."""
    if not args or args[0] in {"show", "status"}:
        show_rag_warmup_info()
        return

    if args[0] == "set":
        if len(args) < 2:
            raise SystemExit("Usage: context-life warmup set <lazy|startup|manual>")
        try:
            path = set_rag_warmup_mode(args[1])
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        CONSOLE.print(f"[bold green]✓[/] Saved warmup mode to [dim]{path}[/]")
        show_rag_warmup_info()
        return

    if args[0] == "prewarm":
        prewarm_rag_now_cli()
        return

    if args[0] in {"interactive", "selector", "select"}:
        run_rag_warmup_interactive()
        return

    raise SystemExit("Usage: context-life warmup [show|set <mode>|prewarm|interactive]")


def _build_info_content():
    """Build the system info renderables (does NOT print)."""
    from rich.columns import Columns
    from rich.console import Group

    from mmcp.config import _default_config_path, get_config

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
    cfg_table.add_row("RAG warmup mode", cfg.rag_warmup_mode)
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
        ("prewarm_rag", "Explicitly warm the RAG model now"),
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
    res_table.add_row("status://rag_warmup", "Warmup mode and MCP impact")
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

    left_group = Group(sys_table, cfg_table, _build_rag_warmup_summary_panel(), dep_table)
    right_group = Group(feat_table, res_table, int_panel)
    columns = Columns([left_group, right_group], expand=True, align="center")

    return Group(
        Align.center(banner_text),
        Align.center(title_text),
        Align.center(_build_rag_warmup_table()),
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
        CONSOLE.print("\n  [bold red]✗ Upgrade failed[/]\n")
        CONSOLE.print(f"  [red]{result.stderr.strip()[:500]}[/]")
        sys.exit(1)


def _build_doctor_content():
    """Build the doctor diagnostics renderables (does NOT print)."""
    from rich.console import Group

    from mmcp.config import _default_config_path, get_config, get_rag_warmup_mode_details

    ver = get_version()
    banner_text = Text(BANNER, style="bold cyan")
    title_text = Text(f"Context-Life (CL) v{ver}  —  LLM Context Optimization MCP Server\n", style="bold white")

    header_panel = Panel("[bold]Environment diagnostics[/]", title="🩺 Doctor", border_style="cyan", box=box.ROUNDED)

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

    warmup = get_rag_warmup_mode_details(cfg.rag_warmup_mode)
    checks.append(("RAG warmup mode", "✅", f"{cfg.rag_warmup_mode} — {warmup['current']['startup_impact']}"))

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
        Align.center(_build_rag_warmup_summary_panel()),
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
        ("context-life tui", "Open the full-screen menu with Config and Metrics sections"),
        ("context-life info", "Show system info, config, dependencies, tools"),
        ("context-life doctor", "Run environment diagnostics"),
        ("context-life warmup", "Explain RAG warmup modes and current setting"),
        ("context-life warmup set <mode>", "Persist RAG warmup mode: lazy, startup, manual"),
        ("context-life warmup interactive", "Open the stateful warmup menu with j/k, enter, esc, q"),
        ("context-life warmup prewarm", "Explicitly warm the RAG model now"),
        ("context-life prewarm", "Shortcut to warm the RAG model now"),
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
    from rich.columns import Columns
    from rich.console import Group

    from mmcp.config import get_config
    from mmcp.session_store import SessionStore

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

    # Non-interactive environments (CI, pipes, containers without TTY)
    # cannot handle the alternate-screen key loop safely. Fall back to a
    # plain render so commands like `context-life info` and `doctor` exit.
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        CONSOLE.print(renderable)
        return

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
                    line = line[: term_width + 40]
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
                import termios
                import tty

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
    """Start the full-screen stateful TUI menu."""
    _show_stateful_menu(_build_main_tui_menu())
