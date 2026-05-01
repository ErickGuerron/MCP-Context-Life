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
from dataclasses import dataclass, field
from importlib.metadata import version as pkg_version
from inspect import Parameter, signature
from io import StringIO
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
    try:
        from colorama import just_fix_windows_console

        just_fix_windows_console()
        changed = True
    except Exception:
        pass
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
    keep_tui: bool = False


@dataclass(slots=True)
class MenuScreen:
    """Stateful menu screen rendered in the TUI."""

    title: str
    subtitle: str
    items: list[MenuItem]
    help_text: str = "↑/↓: navigate • →: select • ←: back • q: quit"
    selected: int = 0
    empty_message: str = "No items available."
    content_builder: Callable[[], object] | None = None
    content_pages_builder: Callable[[], list[DetailPage]] | None = None
    notice: str | None = None
    notice_style: str = "green"
    page_index: int = 0
    scroll_offset: int = 0
    _detail_pages_cache: list[DetailPage] | None = field(default=None, init=False, repr=False)
    _detail_line_cache: dict[tuple[int, int], list[str]] = field(default_factory=dict, init=False, repr=False)


@dataclass(slots=True)
class DetailPage:
    """Single read-only page inside a dense detail view."""

    title: str
    renderable_builder: Callable[[], object]


@dataclass(slots=True)
class MenuActionResult:
    """Side effects requested by a menu action after it completes."""

    back_levels: int = 0
    notice: str | None = None
    notice_style: str = "green"


def _title_case_mode(mode: str) -> str:
    """Format config modes for inline menu labels."""
    return mode.strip().title()


def _current_warmup_mode_label() -> str:
    """Read the current persisted warmup mode for inline config labels."""
    from mmcp.infrastructure.environment.config import get_config

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


def _build_internal_divider(title: str, width: int) -> Text:
    """Render a full-width internal divider that never draws side walls."""
    usable_width = max(1, width)
    clean_title = " ".join(title.split()) or "Section"
    label = f" {clean_title} "

    if len(label) >= usable_width:
        return Text(label[:usable_width], style="bold cyan")

    left = (usable_width - len(label)) // 2
    right = usable_width - len(label) - left
    divider = Text("-" * left, style="dim")
    divider.append(label, style="bold cyan")
    divider.append("-" * right, style="dim")
    return divider


def _detail_section_lines(rows: list[tuple[str, str]]) -> list[str]:
    """Convert compact key/value rows into wrapped linear lines."""
    return [f"[bold]{label}:[/] {value}" for label, value in rows]


def _build_linear_detail_sections(
    sections: list[tuple[str, list[str]]], width: int, empty_message: str = "[dim]No data available.[/]"
) -> Group:
    """Build single-container detail content with internal full-width dividers."""
    items: list[object] = []
    for index, (title, lines) in enumerate(sections):
        if index:
            items.append(Text(""))
        items.append(_build_internal_divider(title, width))
        for line in lines or [empty_message]:
            items.append(_markup_text(line))
    return Group(*items)


def _call_detail_builder(builder: Callable[..., object], width: int):
    """Call detail builders with width when they explicitly support it."""
    try:
        params = list(signature(builder).parameters.values())
    except (TypeError, ValueError):
        params = []

    accepts_width = any(
        param.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD, Parameter.VAR_POSITIONAL)
        for param in params
    )
    return builder(width) if accepts_width else builder()


def _menu_item_display_label(item: MenuItem) -> str:
    """Resolve the runtime label shown for a menu item."""
    if item.inline_value is None:
        return item.label
    return f"{item.label}: {item.inline_value()}"


def get_version() -> str:
    """Get installed version, falling back to __init__ if not pip-installed."""
    try:
        from mmcp import __version__

        return __version__
    except Exception:
        try:
            return pkg_version("context-life")
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
        return False, "not found"


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
    """Build a compact warmup comparison panel."""
    from mmcp.infrastructure.environment.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    lines: list[str] = []
    for mode in ("lazy", "startup", "manual"):
        info = details["modes"][mode]
        label = f"[bold green]{info['label']}[/]" if mode == details["current_mode"] else info["label"]
        if mode == details["current_mode"]:
            label = f"{label} [dim](current)[/]"
        lines.append(
            f"[bold]{label}[/]\n"
            f"  startup → {info['startup_impact']}\n"
            f"  first use → {info['first_use_impact']}\n"
            f"  resources → {info['resource_impact']}"
        )

    return Panel("\n\n".join(lines), title="RAG Warmup Modes", border_style="red", box=box.ROUNDED, padding=(0, 1))


def _build_rag_warmup_summary_panel():
    """Current warmup mode summary panel."""
    from mmcp.infrastructure.environment.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    current = details["current"]
    return Panel(
        f"[bold]Current mode:[/] [green]{details['current_mode']}[/]\n"
        f"[bold]Startup:[/] {current['startup_impact']}\n"
        f"[bold]First RAG use:[/] {current['first_use_impact']}\n"
        f"[bold]Resources:[/] {current['resource_impact']}\n\n"
        "[dim]Persist it with `context-life warmup set <lazy|startup|manual>` or trigger `context-life prewarm`.[/]",
        title="RAG Warmup Status",
        border_style="red",
        box=box.ROUNDED,
    )


def _warmup_status_lines() -> list[str]:
    """Linear warmup summary lines for single-container detail pages."""
    from mmcp.infrastructure.environment.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    current = details["current"]
    return [
        f"[bold]Current mode:[/] [green]{details['current_mode']}[/]",
        f"[bold]Startup:[/] {current['startup_impact']}",
        f"[bold]First RAG use:[/] {current['first_use_impact']}",
        f"[bold]Resources:[/] {current['resource_impact']}",
        "[dim]Persist it with `context-life warmup set <lazy|startup|manual>` or trigger `context-life prewarm`.[/]",
    ]


def _warmup_modes_lines() -> list[str]:
    """Linear warmup comparison lines for single-container detail pages."""
    from mmcp.infrastructure.environment.config import get_config, get_rag_warmup_mode_details

    details = get_rag_warmup_mode_details(get_config().rag_warmup_mode)
    lines: list[str] = []
    for mode in ("lazy", "startup", "manual"):
        info = details["modes"][mode]
        label = f"[bold green]{info['label']}[/]" if mode == details["current_mode"] else info["label"]
        if mode == details["current_mode"]:
            label = f"{label} [dim](current)[/]"
        lines.extend(
            [
                f"[bold]{label}[/]",
                f"startup → {info['startup_impact']}",
                f"first use → {info['first_use_impact']}",
                f"resources → {info['resource_impact']}",
                "",
            ]
        )
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _build_warmup_status_detail_page(width: int):
    """Single-container warmup status page for the stateful TUI."""
    return _build_linear_detail_sections([("Warmup Status", _warmup_status_lines())], width)


def _build_warmup_modes_detail_page(width: int):
    """Single-container warmup modes page for the stateful TUI."""
    return _build_linear_detail_sections([("Warmup Modes", _warmup_modes_lines())], width)


def _render_rag_warmup_interactive_selector():
    """Build the interactive selector screen renderable."""
    return Group(
        _build_rag_warmup_summary_panel(),
        Text(""),
        _build_rag_warmup_table(),
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
                if char == b"K":
                    return "left"
                if char == b"M":
                    return "right"
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
                if next2 == "C":
                    return "right"
                if next2 == "D":
                    return "left"
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


def _get_detail_pages(screen: MenuScreen) -> list[DetailPage]:
    """Resolve read-only detail pages for the current screen."""
    if screen._detail_pages_cache is not None:
        return screen._detail_pages_cache

    if screen.content_pages_builder is not None:
        screen._detail_pages_cache = screen.content_pages_builder()
    elif screen.content_builder is not None:
        screen._detail_pages_cache = [DetailPage(title=screen.title, renderable_builder=screen.content_builder)]
    else:
        screen._detail_pages_cache = []

    return screen._detail_pages_cache


def _invalidate_screen_cache(screen: MenuScreen):
    """Clear cached detail pages and rendered lines for a screen tree."""
    screen._detail_pages_cache = None
    screen._detail_line_cache.clear()
    for item in screen.items:
        if item.submenu is not None:
            _invalidate_screen_cache(item.submenu)


def _detail_body_width() -> int:
    """Stable detail body width inside the centered layout."""
    return min(104, max(72, (CONSOLE.width or 120) - 8))


def _detail_footer_text(screen: MenuScreen, page_count: int) -> str:
    """Shared detail footer text."""
    detail_help = ["↑/↓: scroll"]
    if page_count > 1:
        detail_help.append("→: next page")
        detail_help.append("←: prev/back")
        detail_help.append("PgUp/PgDn: page")
    detail_help.extend(["q: quit"])
    return " • ".join(detail_help)


def _render_detail_page_lines(screen: MenuScreen, page_index: int, content_width: int) -> list[str]:
    """Render and cache ANSI-safe lines for one detail page."""
    cache_key = (page_index, content_width)
    cached = screen._detail_line_cache.get(cache_key)
    if cached is not None:
        return cached

    pages = _get_detail_pages(screen)
    if not pages or page_index < 0 or page_index >= len(pages):
        return []

    lines = _render_renderable_to_lines(
        _call_detail_builder(pages[page_index].renderable_builder, max(40, content_width)),
        max(40, content_width),
    )
    screen._detail_line_cache[cache_key] = lines
    return lines


def _measure_renderable_height(renderable, width: int) -> int:
    """Measure rendered height using the shared ANSI pre-renderer."""
    return max(1, len(_render_renderable_to_lines(renderable, width)))


def _resolve_detail_layout(screen: MenuScreen, path: str, latest_version: str | None = None) -> dict[str, object]:
    """Compute stable detail layout metrics for the active terminal size."""
    term_width = CONSOLE.width or 120
    term_height = CONSOLE.height or 40
    body_width = _detail_body_width()
    content_width = max(40, body_width - 4)

    pages = _get_detail_pages(screen)
    _clamp_detail_page(screen, len(pages))
    footer_text = _detail_footer_text(screen, len(pages))
    footer = Panel(footer_text, border_style="dim", box=box.ROUNDED)
    chrome = Group(
        Align.center(Text(BANNER, style="bold cyan")),
        Align.center(
            Text(f"Context-Life (CL) v{get_version()}  —  LLM Context Optimization MCP Server", style="bold white")
        ),
        Text(""),
        Align.center(_build_tui_header(path, screen.subtitle, latest_version)),
        Text(""),
        Text(""),
        Align.center(footer),
    )
    available_body_height = max(5, term_height - _measure_renderable_height(chrome, term_width))

    if not pages:
        return {
            "pages": pages,
            "body_width": body_width,
            "body_height": available_body_height,
            "viewport_height": max(3, available_body_height - 2),
            "page_lines": [],
            "visible_lines": [""],
            "subtitle": "",
            "footer_text": footer_text,
            "max_offset": 0,
        }

    page = pages[screen.page_index]
    page_lines = _render_detail_page_lines(screen, screen.page_index, content_width)
    content_height = max(1, len(page_lines))
    body_height = min(available_body_height, content_height + 2)
    viewport_height = max(3, body_height - 2)
    max_offset = max(0, len(page_lines) - viewport_height)
    screen.scroll_offset = max(0, min(screen.scroll_offset, max_offset))
    visible_lines = page_lines[screen.scroll_offset : screen.scroll_offset + viewport_height] or [""]

    subtitle = f"Page {screen.page_index + 1}/{len(pages)}"
    if page.title and page.title != screen.title:
        subtitle = f"{subtitle} • {page.title}"
    if max_offset > 0:
        subtitle = (
            f"{subtitle} • scroll {screen.scroll_offset + 1}-"
            f"{min(len(page_lines), screen.scroll_offset + viewport_height)}/{len(page_lines)}"
        )

    return {
        "pages": pages,
        "body_width": body_width,
        "body_height": body_height,
        "viewport_height": viewport_height,
        "page_lines": page_lines,
        "visible_lines": visible_lines,
        "subtitle": subtitle,
        "footer_text": footer_text,
        "max_offset": max_offset,
    }


def _clamp_detail_page(screen: MenuScreen, page_count: int):
    """Keep detail page index in range."""
    if page_count <= 0:
        screen.page_index = 0
        return
    screen.page_index = max(0, min(screen.page_index, page_count - 1))


def _move_detail_page(screen: MenuScreen, delta: int, page_count: int):
    """Move between horizontal detail pages and reset vertical scroll."""
    previous = screen.page_index
    _clamp_detail_page(screen, page_count)
    screen.page_index = max(0, min(screen.page_index + delta, max(0, page_count - 1)))
    if screen.page_index != previous:
        screen.scroll_offset = 0


def _move_detail_scroll(screen: MenuScreen, delta: int, max_offset: int):
    """Move vertical scroll inside a dense detail page."""
    screen.scroll_offset = max(0, min(screen.scroll_offset + delta, max_offset))


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


def _markup_pairs(rows: list[tuple[str, str]]) -> str:
    """Render compact key/value lines using Rich markup."""
    return "\n".join(f"[bold]{label}:[/] {value}" for label, value in rows)


def _markup_text(markup: str) -> Text:
    """Build wrapped Rich text so long content never blows panel borders."""
    text = Text.from_markup(markup)
    text.overflow = "fold"
    text.no_wrap = False
    return text


def _stack_renderables(*renderables: object) -> Group:
    """Stack renderables vertically with breathing room between sections."""
    items: list[object] = []
    for renderable in renderables:
        if renderable is None:
            continue
        if items:
            items.append(Text(""))
        items.append(renderable)
    return Group(*items)


def _compact_panel(title: str, rows: list[tuple[str, str]], border_style: str = "cyan"):
    """Small reusable panel for compact status sections."""
    body = Group(*[_markup_text(f"[bold]{label}:[/] {value}") for label, value in rows])
    return Panel(body, title=title, border_style=border_style, box=box.ROUNDED, padding=(0, 1))


def _compact_list_panel(title: str, lines: list[str], border_style: str = "cyan"):
    """Small reusable panel for compact bullet-like sections."""
    body = Group(*[_markup_text(line) for line in lines]) if lines else _markup_text("[dim]No data available.[/]")
    return Panel(body, title=title, border_style=border_style, box=box.ROUNDED, padding=(0, 1))


def _build_menu_panel(screen: MenuScreen, path: str, latest_version: str | None = None):
    """Build the full stateful menu renderable."""
    _clamp_menu_selection(screen)

    rows: list[object] = []
    if screen.notice:
        rows.append(
            Panel(screen.notice, title="Status", border_style=screen.notice_style, box=box.ROUNDED, padding=(0, 1))
        )
        rows.append(Text(""))

    if screen.content_builder is not None or screen.content_pages_builder is not None:
        detail_layout = _resolve_detail_layout(screen, path, latest_version)
        pages = detail_layout["pages"]

        if pages:
            page_group = Text.from_ansi("\n".join(detail_layout["visible_lines"]))
            page_group.no_wrap = True
            page_group.overflow = "ignore"
            rows.append(page_group)
        else:
            rows.append(Text(screen.empty_message, style="dim"))
    elif screen.items:
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

    body_width = _detail_body_width()
    is_detail_screen = screen.content_builder is not None or screen.content_pages_builder is not None
    if is_detail_screen:
        detail_layout = _resolve_detail_layout(screen, path, latest_version)
        body = Panel(
            Group(*rows),
            title=screen.title,
            subtitle=detail_layout["subtitle"] or screen.subtitle,
            border_style="cyan",
            box=box.ROUNDED,
            width=body_width,
            height=detail_layout["body_height"],
            padding=(0, 1),
        )
        footer_text = _detail_footer_text(screen, len(_get_detail_pages(screen)))
    else:
        body = Panel(
            Group(*rows),
            title=screen.title,
            subtitle="Use → or enter to select",
            border_style="cyan",
            box=box.ROUNDED,
            width=body_width,
        )
        footer_text = screen.help_text

    footer = Panel(footer_text, border_style="dim", box=box.ROUNDED)

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
    keep_tui: bool = False,
) -> MenuActionResult | None:
    """Temporarily leave the menu screen, run an action, then return."""
    if keep_tui:
        return action()

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
                if current.content_builder is not None or current.content_pages_builder is not None:
                    path = "  ›  ".join(menu.title for menu in stack)
                    detail_layout = _resolve_detail_layout(current, path, state["latest_version"])
                    _move_detail_scroll(current, 1, detail_layout["max_offset"])
                else:
                    _move_menu_selection(current, 1)
                paint()
                continue
            if key in ("k", "up"):
                if current.content_builder is not None or current.content_pages_builder is not None:
                    path = "  ›  ".join(menu.title for menu in stack)
                    detail_layout = _resolve_detail_layout(current, path, state["latest_version"])
                    _move_detail_scroll(current, -1, detail_layout["max_offset"])
                else:
                    _move_menu_selection(current, -1)
                paint()
                continue
            if current.content_pages_builder is not None:
                page_count = len(_get_detail_pages(current))
                if key in ("right", "pgdn") and current.page_index < max(0, page_count - 1):
                    _move_detail_page(current, 1, page_count)
                    paint()
                    continue
                if key in ("left", "pgup"):
                    if current.page_index > 0:
                        _move_detail_page(current, -1, page_count)
                        paint()
                        continue
                    if len(stack) > 1:
                        stack.pop()
                        paint()
                        continue
            if key == "q":
                break
            if key == "left" or key == "esc":
                if len(stack) == 1:
                    break
                stack.pop()
                paint()
                continue
            if key not in ("enter", "right") or not current.items:
                continue

            item = current.items[current.selected]
            if item.submenu is not None:
                _clamp_menu_selection(item.submenu)
                stack.append(item.submenu)
                paint()
                continue

            if item.action is not None:
                result = _run_menu_action(
                    item.action,
                    write,
                    flush,
                    show_cursor,
                    exit_alt_screen,
                    enter_alt_screen,
                    hide_cursor,
                    item.keep_tui,
                )
                if result is not None:
                    _invalidate_screen_cache(stack[0])
                    for _ in range(min(result.back_levels, max(0, len(stack) - 1))):
                        stack.pop()
                    if result.notice and stack:
                        stack[-1].notice = result.notice
                        stack[-1].notice_style = result.notice_style
                paint()
    finally:
        write(show_cursor + exit_alt_screen)
        flush()


def show_rag_warmup_info():
    """Display RAG warmup mode details."""
    _show_in_scrollable_screen(_build_warmup_status_content(), title="RAG Warmup")


def _build_warmup_status_content():
    """Compact single-screen warmup status layout."""
    return _stack_renderables(
        _build_rag_warmup_summary_panel(),
        _build_rag_warmup_table(),
    )


def _build_warmup_status_pages() -> list[DetailPage]:
    """Split warmup status into horizontally navigable pages."""
    return [
        DetailPage(title="Status", renderable_builder=_build_warmup_status_detail_page),
        DetailPage(title="Modes", renderable_builder=_build_warmup_modes_detail_page),
    ]


def _build_detail_screen(title: str, subtitle: str, content_builder: Callable[[], object]) -> MenuScreen:
    """Create a read-only detail screen embedded in the TUI layout."""
    return MenuScreen(
        title=title,
        subtitle=subtitle,
        items=[],
        help_text="←: back • q: quit",
        content_builder=content_builder,
    )


def _build_paged_detail_screen(
    title: str, subtitle: str, content_pages_builder: Callable[[], list[DetailPage]]
) -> MenuScreen:
    """Create a read-only detail screen with horizontal paging."""
    return MenuScreen(
        title=title,
        subtitle=subtitle,
        items=[],
        help_text="↑/↓: scroll • PgUp/PgDn: page • ←: back • q: quit",
        content_pages_builder=content_pages_builder,
    )


def set_rag_warmup_mode(mode: str) -> str:
    """Persist a new RAG warmup mode."""
    from mmcp.infrastructure.environment.config import (
        VALID_RAG_WARMUP_MODES,
        get_config,
        normalize_rag_warmup_mode,
        save_config,
    )

    normalized = normalize_rag_warmup_mode(mode)
    if normalized != mode.strip().lower() or normalized not in VALID_RAG_WARMUP_MODES:
        raise ValueError(f"Invalid warmup mode: {mode}. Use lazy, startup, or manual.")

    cfg = get_config()
    cfg.rag_warmup_mode = normalized
    path = save_config(cfg)
    return str(path)


def _show_saved_warmup_mode(mode: str):
    """Persist a warmup mode and return the inline status message."""
    from mmcp.infrastructure.environment.config import get_config

    current_mode = get_config().rag_warmup_mode
    path = set_rag_warmup_mode(mode)

    if current_mode == mode:
        return f"[bold]Warmup mode:[/] [green]{mode}[/]\n[dim]Already active. Config remains at {path}[/]"
    else:
        return f"[bold]Warmup mode updated:[/] [yellow]{current_mode}[/] → [green]{mode}[/]\n[dim]Saved in {path}[/]"


def _set_warmup_mode_and_return(mode: str) -> MenuActionResult:
    """Persist the warmup mode and return to Config."""
    return MenuActionResult(back_levels=1, notice=_show_saved_warmup_mode(mode))


def _prewarm_rag_now_and_return() -> MenuActionResult:
    """Prewarm RAG and keep the feedback inline inside the TUI."""
    from mmcp.presentation.mcp.server import prewarm_rag_now

    result = prewarm_rag_now()
    message = (
        f"[bold]Mode:[/] [green]{result['mode']}[/]\n"
        f"[bold]Already loaded:[/] {'yes' if result['already_loaded'] else 'no'}\n"
        f"[bold]Model loaded:[/] {'yes' if result['model_loaded'] else 'no'}\n"
        f"[dim]{result['message']}[/]"
    )
    return MenuActionResult(back_levels=1, notice=message)


def _build_warmup_menu() -> MenuScreen:
    """Warmup submenu integrated into the stateful TUI."""
    return MenuScreen(
        title="Config / Warmup",
        subtitle="Inspect and configure RAG warmup without leaving the navigable menu flow.",
        items=[
            MenuItem(
                "Show warmup status",
                "See current mode, startup impact, and mode comparison.",
                submenu=_build_paged_detail_screen(
                    "RAG Warmup Status",
                    "Compact warmup pages that stay navigable inside the stable TUI layout.",
                    _build_warmup_status_pages,
                ),
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
            MenuItem(
                "Prewarm now",
                "Load the model immediately without changing the saved mode.",
                _prewarm_rag_now_and_return,
            ),
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
            MenuItem(
                "Upgrade Context-Life",
                "Install the latest GitHub release when you are ready.",
                lambda: do_upgrade(inside_tui=True),
                keep_tui=True,
            ),
        ],
    )


def _build_metrics_menu() -> MenuScreen:
    """First-level diagnostics and metrics section."""
    return MenuScreen(
        title="Metrics",
        subtitle="Status, diagnostics, and runtime visibility for the current environment.",
        items=[
            MenuItem(
                "Info",
                "System, config, dependencies, tools, and resources overview.",
                submenu=_build_paged_detail_screen(
                    "Info",
                    "Compact system pages with horizontal navigation for dense sections.",
                    _build_info_pages,
                ),
            ),
            MenuItem(
                "Health",
                "Environment diagnostics and readiness checks.",
                submenu=_build_paged_detail_screen(
                    "Health",
                    "Readiness checks grouped into compact horizontally navigable pages.",
                    _build_doctor_pages,
                ),
            ),
            MenuItem(
                "Telemetry",
                "Weekly usage, savings, and budget tracking dashboard.",
                submenu=_build_detail_screen(
                    "Telemetry",
                    "Scrollable telemetry dashboard with summary and model usage kept together.",
                    _build_telemetry_content,
                ),
            ),
        ],
    )


def _build_main_tui_menu() -> MenuScreen:
    """Top-level stateful TUI menu."""
    return MenuScreen(
        title="Main Menu",
        subtitle="Pick a section with ↑/↓ and use →/enter to open, ← to go back.",
        items=[
            MenuItem("Config", "Warmup settings and configurable operational actions.", submenu=_build_config_menu()),
            MenuItem("Metrics", "Info, health, telemetry, and diagnostic resources.", submenu=_build_metrics_menu()),
        ],
        help_text="↑/↓: navigate • →/enter: select • ←: back • q: quit",
    )


def prewarm_rag_now_cli():
    """Explicit CLI action to prewarm the RAG model immediately."""
    from mmcp.presentation.mcp.server import prewarm_rag_now

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
            message = _show_saved_warmup_mode(args[1])
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        CONSOLE.print(Panel(message, title="⚙️ Warmup Updated", border_style="green", box=box.ROUNDED))
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
    """Build the compact system info renderables (does NOT print)."""
    from mmcp.infrastructure.environment.config import _default_config_path, get_config

    cfg = get_config()
    deps = [
        ("mcp", "mcp"),
        ("tiktoken", "tiktoken"),
        ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"),
        ("pyarrow", "pyarrow"),
        ("rich", "rich"),
    ]
    dependency_lines: list[str] = []
    for name, importable in deps:
        ok, ver = _safe_import_check(importable)
        status = "[green]installed[/]" if ok else "[red]missing[/]"
        dependency_lines.append(f"[bold]{name}[/] — {status} • [dim]{ver}[/]")

    tool_lines = [
        "[bold]tokens[/] — count_tokens_tool, count_messages_tokens_tool",
        "[bold]history[/] — optimize_messages",
        "[bold]rag[/] — search_context, index_knowledge, rag_stats, clear_knowledge",
        "[bold]runtime[/] — prewarm_rag, cache_context, reset_token_budget",
        "[bold]advice[/] — get_orchestration_advice",
    ]
    resource_lines = [
        "[bold]status://token_budget[/] — token budget consumption",
        "[bold]cache://status[/] — cache hit/miss stats",
        "[bold]rag://stats[/] — RAG knowledge base info",
        "[bold]status://rag_warmup[/] — warmup mode and MCP impact",
        "[bold]status://orchestrator[/] — detected orchestrator",
        "[bold]status://orchestration[/] — orchestration contract",
    ]

    return _stack_renderables(
        _compact_panel(
            "🖥 System",
            [
                ("Version", f"v{get_version()}"),
                ("Python", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
                ("OS", platform.system()),
                ("Arch", platform.machine()),
            ],
            border_style="blue",
        ),
        _compact_panel(
            "⚙️ Config",
            [
                ("Config file", str(_default_config_path())),
                ("Data dir", str(cfg.resolve_data_dir())),
                ("RAG DB", cfg.resolve_rag_db_path()),
                ("Warmup", cfg.rag_warmup_mode),
                ("Top K / Score", f"{cfg.rag_top_k} / {cfg.rag_min_score}"),
                ("Token budget", f"{cfg.token_budget_default:,}"),
            ],
            border_style="white",
        ),
        _build_rag_warmup_summary_panel(),
        _build_rag_warmup_table(),
        _compact_list_panel("📦 Dependencies", dependency_lines, border_style="green"),
        _compact_list_panel("⚡ Tools", tool_lines, border_style="magenta"),
        _compact_list_panel("📊 Resources", resource_lines, border_style="yellow"),
        _compact_list_panel(
            "🔌 Integration",
            [
                '[bold]"context-life"[/] { type: "local" }',
                '[bold]command[/] ["context-life"]',
                "[bold]enabled[/] true",
            ],
            border_style="dim",
        ),
    )


def _build_info_pages() -> list[DetailPage]:
    """Split dense info data into compact navigable pages."""
    from mmcp.infrastructure.environment.config import _default_config_path, get_config

    cfg = get_config()
    deps = [
        ("mcp", "mcp"),
        ("tiktoken", "tiktoken"),
        ("lancedb", "lancedb"),
        ("sentence-transformers", "sentence_transformers"),
        ("pyarrow", "pyarrow"),
        ("rich", "rich"),
    ]
    dependency_lines: list[str] = []
    for name, importable in deps:
        ok, ver = _safe_import_check(importable)
        status = "[green]installed[/]" if ok else "[red]missing[/]"
        dependency_lines.append(f"[bold]{name}[/] — {status} • [dim]{ver}[/]")

    tool_lines = [
        "[bold]tokens[/] — count_tokens_tool, count_messages_tokens_tool",
        "[bold]history[/] — optimize_messages",
        "[bold]rag[/] — search_context, index_knowledge, rag_stats, clear_knowledge",
        "[bold]runtime[/] — prewarm_rag, cache_context, reset_token_budget",
        "[bold]advice[/] — get_orchestration_advice",
    ]
    resource_lines = [
        "[bold]status://token_budget[/] — token budget consumption",
        "[bold]cache://status[/] — cache hit/miss stats",
        "[bold]rag://stats[/] — RAG knowledge base info",
        "[bold]status://rag_warmup[/] — warmup mode and MCP impact",
        "[bold]status://orchestrator[/] — detected orchestrator",
        "[bold]status://orchestration[/] — orchestration contract",
    ]

    return [
        DetailPage(
            title="Overview",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [
                    (
                        "🖥 System",
                        _detail_section_lines(
                            [
                                ("Version", f"v{get_version()}"),
                                (
                                    "Python",
                                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                                ),
                                ("OS", platform.system()),
                                ("Arch", platform.machine()),
                            ]
                        ),
                    ),
                    (
                        "⚙️ Config",
                        _detail_section_lines(
                            [
                                ("Config file", str(_default_config_path())),
                                ("Data dir", str(cfg.resolve_data_dir())),
                                ("RAG DB", cfg.resolve_rag_db_path()),
                                ("Warmup", cfg.rag_warmup_mode),
                                ("Top K / Score", f"{cfg.rag_top_k} / {cfg.rag_min_score}"),
                                ("Token budget", f"{cfg.token_budget_default:,}"),
                            ]
                        ),
                    ),
                ],
                width,
            ),
        ),
        DetailPage(
            title="Warmup",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [
                    ("Warmup Status", _warmup_status_lines()),
                    ("Warmup Modes", _warmup_modes_lines()),
                ],
                width,
            ),
        ),
        DetailPage(
            title="Runtime Surface",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [
                    ("📦 Dependencies", dependency_lines),
                    ("⚡ Tools", tool_lines),
                    ("📊 Resources", resource_lines),
                    (
                        "🔌 Integration",
                        [
                            '[bold]"context-life"[/] { type: "local" }',
                            '[bold]command[/] ["context-life"]',
                            "[bold]enabled[/] true",
                        ],
                    ),
                ],
                width,
            ),
        ),
    ]


def show_info():
    """Display system info inside a scrollable alternate screen."""
    content = _build_info_content()
    _show_in_scrollable_screen(content, title="System Info")


def do_upgrade(target_version: str | None = None, dry_run: bool = False, inside_tui: bool = False):
    """Compatibility wrapper for the dedicated upgrade flow."""
    from .upgrade import do_upgrade as _do_upgrade

    return _do_upgrade(target_version=target_version, dry_run=dry_run, inside_tui=inside_tui)


def _build_doctor_content():
    """Build compact doctor diagnostics renderables (does NOT print)."""
    from mmcp.infrastructure.environment.config import _default_config_path, get_config, get_rag_warmup_mode_details

    ver = get_version()
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

    has_errors = any(s == "❌" for _, s, _ in checks)
    summary_panel = Panel(
        "[bold red]Some checks failed.[/] Fix the red items and run again."
        if has_errors
        else "[bold green]All checks passed.[/] Context-Life is ready to use.",
        title="🩺 Health Summary",
        border_style="red" if has_errors else "green",
        box=box.ROUNDED,
        padding=(0, 1),
    )

    runtime_checks = checks[:2] + [checks[-1]]
    dependency_checks = checks[2:8]
    storage_checks = checks[8:11]
    release_checks = checks[11:]

    def _lines_for(items: list[tuple[str, str, str]]) -> list[str]:
        return [f"{status} [bold]{name}[/] — [dim]{detail}[/]" for name, status, detail in items]

    return _stack_renderables(
        summary_panel,
        _build_rag_warmup_summary_panel(),
        _compact_list_panel("Runtime", _lines_for(runtime_checks), border_style="cyan"),
        _compact_list_panel("Dependencies", _lines_for(dependency_checks), border_style="green"),
        _compact_list_panel("Storage", _lines_for(storage_checks), border_style="yellow"),
        _compact_list_panel("Release", _lines_for(release_checks), border_style="magenta"),
        _compact_panel(
            "Paths",
            [
                ("Config file", str(_default_config_path())),
                ("Data directory", str(cfg.resolve_data_dir())),
                ("RAG path", str(rag_path)),
            ],
            border_style="dim",
        ),
    )


def _build_doctor_pages() -> list[DetailPage]:
    """Split health diagnostics into smaller pages."""
    from mmcp.infrastructure.environment.config import _default_config_path, get_config, get_rag_warmup_mode_details

    ver = get_version()
    checks: list[tuple[str, str, str]] = []
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", "✅" if py_ok else "❌", f"{py_ver} {'(>= 3.10 required)' if not py_ok else ''}"))
    checks.append(("Installed version", "✅", f"v{ver}"))

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

    cfg_path = _default_config_path()
    cfg_exists = cfg_path.exists()
    checks.append(
        ("Config file", "✅" if cfg_exists else "ℹ️", f"{cfg_path}" + (" (using defaults)" if not cfg_exists else ""))
    )

    cfg = get_config()
    data_dir = cfg.resolve_data_dir()
    checks.append(("Data directory", "✅", str(data_dir)))

    rag_path = Path(cfg.resolve_rag_db_path())
    rag_writable = os.access(rag_path.parent, os.W_OK) if rag_path.parent.exists() else False
    checks.append(
        ("LanceDB path", "✅" if rag_writable else "⚠️", f"{rag_path}" + (" (not writable)" if not rag_writable else ""))
    )

    warmup = get_rag_warmup_mode_details(cfg.rag_warmup_mode)
    checks.append(("RAG warmup mode", "✅", f"{cfg.rag_warmup_mode} — {warmup['current']['startup_impact']}"))

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

    has_errors = any(s == "❌" for _, s, _ in checks)

    runtime_checks = checks[:2] + [checks[-1]]
    dependency_checks = checks[2:8]
    storage_checks = checks[8:11]
    release_checks = checks[11:]

    def _lines_for(items: list[tuple[str, str, str]]) -> list[str]:
        return [f"{status} [bold]{name}[/] — [dim]{detail}[/]" for name, status, detail in items]

    return [
        DetailPage(
            title="Summary",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [
                    (
                        "Health Summary",
                        [
                            "[bold red]Some checks failed.[/] Fix the red items and run again."
                            if has_errors
                            else "[bold green]All checks passed.[/] Context-Life is ready to use."
                        ],
                    )
                ],
                width,
            ),
        ),
        DetailPage(
            title="Warmup",
            renderable_builder=_build_warmup_status_detail_page,
        ),
        DetailPage(
            title="Checks",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [("Runtime", _lines_for(runtime_checks)), ("Dependencies", _lines_for(dependency_checks))],
                width,
            ),
        ),
        DetailPage(
            title="Storage + Paths",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [
                    ("Storage", _lines_for(storage_checks)),
                    ("Release", _lines_for(release_checks)),
                    (
                        "Paths",
                        _detail_section_lines(
                            [
                                ("Config file", str(_default_config_path())),
                                ("Data directory", str(cfg.resolve_data_dir())),
                                ("RAG path", str(rag_path)),
                            ]
                        ),
                    ),
                ],
                width,
            ),
        ),
    ]


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
    """Build the compact telemetry dashboard renderables (does NOT print)."""
    from mmcp.infrastructure.environment.config import get_config
    from mmcp.infrastructure.persistence.session_store import SessionStore

    cfg = get_config()
    store = SessionStore(cfg.resolve_cache_db_path())

    weekly = store.get_weekly_usage()
    recent = store.get_recent_stats(days=7)

    accounted_input = recent["accounted_input_tokens"]
    output_tokens = recent["output_tokens"]
    saved_tokens = recent["saved_tokens"]
    savings_pct = (saved_tokens / accounted_input * 100) if accounted_input > 0 else 0.0
    budget = cfg.token_budget_default
    usage_lines: list[str] = []
    if not weekly:
        usage_lines.append("[dim]No usage data for the last 7 days.[/]")
    else:
        sorted_models = sorted(weekly.items(), key=lambda item: item[1]["accounted_input_tokens"], reverse=True)
        for model_name, data in sorted_models[:6]:
            used = data["accounted_input_tokens"]
            transformed = data["output_tokens"]
            saved = data["saved_tokens"]
            usage_lines.append(
                f"[bold]{model_name}[/] — input {format_big_number(used)} • "
                f"output {format_big_number(transformed)} • saved {format_big_number(saved)}"
            )
        if len(sorted_models) > 6:
            usage_lines.append(f"[dim]+ {len(sorted_models) - 6} more model(s) not shown[/]")

    return _stack_renderables(
        _compact_panel(
            "💰 Telemetry",
            [
                ("Accounted input", format_big_number(accounted_input)),
                ("Output", format_big_number(output_tokens)),
                ("Saved / reused", f"[green]{format_big_number(saved_tokens)}[/]"),
                ("Savings vs input", f"[bold green]{savings_pct:.1f}%[/]"),
            ],
            border_style="green",
        ),
        _compact_panel(
            "📅 Budget reference",
            [
                ("Window", "Rolling 7 days"),
                ("Default request budget", format_big_number(budget)),
                ("Tracked models", str(len(weekly))),
            ],
            border_style="blue",
        ),
        _compact_list_panel("Model usage", usage_lines, border_style="cyan"),
        _compact_list_panel(
            "Notes",
            [
                "Rolling 7-day window recalculates automatically.",
                "Telemetry tracks Context-Life MCP tool calls only, not host LLM billing/cache telemetry.",
                "Input/output/saved now use explicit accounting semantics.",
                "Budget is a per-request reference ceiling, not a weekly quota.",
            ],
            border_style="dim",
        ),
    )


def _build_telemetry_pages() -> list[DetailPage]:
    """Split telemetry into overview and per-model usage pages."""
    from mmcp.infrastructure.environment.config import get_config
    from mmcp.infrastructure.persistence.session_store import SessionStore

    cfg = get_config()
    store = SessionStore(cfg.resolve_cache_db_path())

    weekly = store.get_weekly_usage()
    recent = store.get_recent_stats(days=7)

    accounted_input = recent["accounted_input_tokens"]
    output_tokens = recent["output_tokens"]
    saved_tokens = recent["saved_tokens"]
    savings_pct = (saved_tokens / accounted_input * 100) if accounted_input > 0 else 0.0
    budget = cfg.token_budget_default
    usage_lines: list[str] = []
    if not weekly:
        usage_lines.append("[dim]No usage data for the last 7 days.[/]")
    else:
        sorted_models = sorted(weekly.items(), key=lambda item: item[1]["accounted_input_tokens"], reverse=True)
        for model_name, data in sorted_models:
            used = data["accounted_input_tokens"]
            transformed = data["output_tokens"]
            saved = data["saved_tokens"]
            usage_lines.append(
                f"[bold]{model_name}[/] — input {format_big_number(used)} • "
                f"output {format_big_number(transformed)} • saved {format_big_number(saved)}"
            )

    return [
        DetailPage(
            title="Overview",
            renderable_builder=lambda: _stack_renderables(
                _compact_panel(
                    "💰 Telemetry",
                    [
                        ("Accounted input", format_big_number(accounted_input)),
                        ("Output", format_big_number(output_tokens)),
                        ("Saved / reused", f"[green]{format_big_number(saved_tokens)}[/]"),
                        ("Savings vs input", f"[bold green]{savings_pct:.1f}%[/]"),
                    ],
                    border_style="green",
                ),
                _compact_panel(
                    "📅 Budget reference",
                    [
                        ("Window", "Rolling 7 days"),
                        ("Default request budget", format_big_number(budget)),
                        ("Tracked models", str(len(weekly))),
                    ],
                    border_style="blue",
                ),
            ),
        ),
        DetailPage(
            title="Model Usage",
            renderable_builder=lambda: _stack_renderables(
                _compact_list_panel("Model usage", usage_lines, border_style="cyan"),
                _compact_list_panel(
                    "Notes",
                    [
                        "Rolling 7-day window recalculates automatically.",
                        "Telemetry tracks Context-Life MCP tool calls only, not host LLM billing/cache telemetry.",
                        "Input/output/saved now use explicit accounting semantics.",
                        "Budget is a per-request reference ceiling, not a weekly quota.",
                    ],
                    border_style="dim",
                ),
            ),
        ),
    ]


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
            footer = f"  ↑/↓/j/k scroll • PgUp/PgDn jump • {pos_pct}%  |  ESC/b/q → back"
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

            # Clamp BEFORE comparing -- avoids repaint if already at boundary
            scroll_offset = max(0, min(scroll_offset, max_offset))
            if scroll_offset != prev_offset:
                paint()
    finally:
        write(SHOW_CURSOR + EXIT_ALT_SCREEN)
        flush()


def do_tui():
    """Start the full-screen stateful TUI menu."""
    _show_stateful_menu(_build_main_tui_menu())
