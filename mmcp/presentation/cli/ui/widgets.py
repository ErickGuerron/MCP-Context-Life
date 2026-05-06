"""Rich widget builders — Panel, Table, Text constructs for the CLI UI."""

from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

# ---------------------------------------------------------------------------
# Shared layout helpers (used by widget builders)
# ---------------------------------------------------------------------------


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
# RAG Warmup widgets
# ---------------------------------------------------------------------------


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


def _render_rag_warmup_interactive_selector():
    """Build the interactive selector screen renderable."""
    return Group(
        _build_rag_warmup_summary_panel(),
        Text(""),
        _build_rag_warmup_table(),
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
