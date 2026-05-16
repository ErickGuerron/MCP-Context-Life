"""Full-screen rendering and layout computation for the stateful CLI TUI."""

from __future__ import annotations

from io import StringIO

from rich import box
from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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

CONSOLE = Console()


# ---------------------------------------------------------------------------
# Shared layout helpers
# ---------------------------------------------------------------------------


def _render_renderable_to_lines(renderable, width: int) -> list[str]:
    """Pre-render a Rich renderable into ANSI-safe lines."""
    temp_buffer = StringIO()
    temp_console = Console(file=temp_buffer, width=width, force_terminal=True)
    temp_console.print(renderable)
    lines = temp_buffer.getvalue().split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def _markup_text(markup: str) -> Text:
    """Build wrapped Rich text so long content never blows panel borders."""
    text = Text.from_markup(markup)
    text.overflow = "fold"
    text.no_wrap = False
    return text


def _markup_pairs(rows: list[tuple[str, str]]) -> str:
    """Render compact key/value lines using Rich markup."""
    return "\n".join(f"[bold]{label}:[/] {value}" for label, value in rows)


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


# ---------------------------------------------------------------------------
# Layout computation
# ---------------------------------------------------------------------------


def get_version() -> str:
    """Get installed version, falling back to __init__ if not pip-installed."""
    try:
        from mmcp import __version__

        return __version__
    except Exception:
        try:
            from importlib.metadata import version as pkg_version

            return pkg_version("context-life")
        except Exception:
            return "dev"


def _detail_body_width() -> int:
    """Stable detail body width inside the centered layout."""
    return min(104, max(72, (CONSOLE.width or 120) - 8))


def _measure_renderable_height(renderable, width: int) -> int:
    """Measure rendered height using the shared ANSI pre-renderer."""
    return max(1, len(_render_renderable_to_lines(renderable, width)))


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


def _detail_footer_text(screen_title: str, page_count: int) -> str:
    """Shared detail footer text."""
    detail_help = ["↑/↓: scroll"]
    if page_count > 1:
        detail_help.append("→: next page")
        detail_help.append("←: prev/back")
        detail_help.append("PgUp/PgDn: page")
    detail_help.extend(["q: quit"])
    return " • ".join(detail_help)


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


def _resolve_detail_layout(
    screen_title: str,
    screen_subtitle: str,
    page_lines: list[str],
    page_index: int,
    scroll_offset: int,
    latest_version: str | None = None,
) -> dict[str, object]:
    """Compute stable detail layout metrics for the active terminal size."""
    term_width = CONSOLE.width or 120
    term_height = CONSOLE.height or 40
    body_width = _detail_body_width()

    footer_text = _detail_footer_text(screen_title, len(page_lines) if page_lines else 0)
    footer = Panel(footer_text, border_style="dim", box=box.ROUNDED)
    chrome = Group(
        Align.center(Text(BANNER, style="bold cyan")),
        Align.center(
            Text(f"Context-Life (CL) v{get_version()}  —  LLM Context Optimization MCP Server", style="bold white")
        ),
        Text(""),
        Align.center(_build_tui_header(path="", subtitle=screen_subtitle, latest_version=latest_version)),
        Text(""),
        Text(""),
        Align.center(footer),
    )
    available_body_height = max(5, term_height - _measure_renderable_height(chrome, term_width))

    if not page_lines:
        return {
            "body_width": body_width,
            "body_height": available_body_height,
            "viewport_height": max(3, available_body_height - 2),
            "page_lines": [],
            "visible_lines": [""],
            "subtitle": "",
            "footer_text": footer_text,
            "max_offset": 0,
        }

    content_height = max(1, len(page_lines))
    body_height = min(available_body_height, content_height + 2)
    viewport_height = max(3, body_height - 2)
    max_offset = max(0, len(page_lines) - viewport_height)
    scroll_offset = max(0, min(scroll_offset, max_offset))
    visible_lines = page_lines[scroll_offset : scroll_offset + viewport_height] or [""]

    subtitle = f"Page {page_index + 1}/{len(page_lines)}"
    if max_offset > 0:
        scroll_end = min(len(page_lines), scroll_offset + viewport_height)
        subtitle = f"{subtitle} • scroll {scroll_offset + 1}-{scroll_end}/{len(page_lines)}"

    return {
        "body_width": body_width,
        "body_height": body_height,
        "viewport_height": viewport_height,
        "page_lines": page_lines,
        "visible_lines": visible_lines,
        "subtitle": subtitle,
        "footer_text": footer_text,
        "max_offset": max_offset,
    }
