"""Application layer: CLI command handlers.

These are application services that coordinate domain logic and presentation.
They are thin orchestrators — they don't implement business logic themselves.
"""

from __future__ import annotations

import sys

from rich import box

from .ui import CONSOLE


def do_upgrade(target_version: str | None = None, dry_run: bool = False, inside_tui: bool = False):
    """Compatibility wrapper for the dedicated upgrade flow."""
    from .upgrade import do_upgrade as _do_upgrade

    return _do_upgrade(target_version=target_version, dry_run=dry_run, inside_tui=inside_tui)


def do_doctor():
    """Run environment diagnostics inside a scrollable alternate screen."""
    from .diagnostics import do_doctor as _do_doctor

    _do_doctor()


def do_tui():
    """Start the full-screen stateful TUI menu."""
    import mmcp.presentation.cli.cli as cli_module

    cli_module._show_stateful_menu(cli_module._build_main_tui_menu())


def show_version():
    """Print version string."""
    from .cli import get_version

    ver = get_version()
    CONSOLE.print(f"[bold cyan]context-life[/] [green]v{ver}[/]")


def show_help():
    """Print usage help."""
    from rich.align import Align
    from rich.table import Table

    from .cli import print_banner

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


def show_info():
    """Display system info inside a scrollable alternate screen."""
    from .diagnostics import show_info as _show_info

    _show_info()


def show_telemetry_dashboard():
    """Display the telemetry dashboard inside a scrollable alternate screen."""
    from .diagnostics import show_telemetry_dashboard as _show_telemetry

    _show_telemetry()


def prewarm_rag_now_cli():
    """Explicit CLI action to prewarm the RAG model immediately."""
    from .warmup import prewarm_rag_now_cli as _prewarm

    _prewarm()


def run_rag_warmup_interactive(input_fn=None):
    """Open the warmup submenu using the shared stateful menu architecture."""
    from .warmup import run_rag_warmup_interactive as _run_interactive

    _run_interactive()


def do_rag_warmup_command(args: list[str]):
    """Handle `context-life warmup ...` subcommands."""
    from .warmup import do_rag_warmup_command as _do_warmup

    _do_warmup(args)


# ---------------------------------------------------------------------------
# Scrollable screen helper (used by diagnostics and telemetry)
# ---------------------------------------------------------------------------


def _show_in_scrollable_screen(renderable, title: str = "View"):
    """
    Display a Rich renderable inside an alternate screen buffer with
    keyboard-controlled vertical scrolling.

    Uses direct ANSI terminal writes instead of Rich Live for
    zero-overhead, buttery smooth scrolling (like less/vim).
    """
    from io import StringIO

    from rich.console import Console as _Console

    from .ui import _strip_ansi_len

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

    # Strip trailing empty lines -- Rich adds them and they inflate the
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
            footer = f"  ↑/↓/j/k scroll • PgUp/PgDn jump • {pos_pct}%  |  ESC/b/q → back"
        else:
            footer = "  All content visible  |  ESC/b/q → back"

        write(f"\033[{term_height};1H\033[2K\033[2;3m{footer.center(term_width)}\033[0m")
        flush()

    # Step 3: Enter alternate screen, paint, handle input, exit
    try:
        from .ui import _read_scroll_key

        write(ENTER_ALT_SCREEN + HIDE_CURSOR)
        flush()
        paint()

        while True:
            c = _read_scroll_key()
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

            # Clamp BEFORE comparing -- avoids repaint if already at boundary
            scroll_offset = max(0, min(scroll_offset, max_offset))
            if scroll_offset != prev_offset:
                paint()
    finally:
        write(SHOW_CURSOR + EXIT_ALT_SCREEN)
        flush()
