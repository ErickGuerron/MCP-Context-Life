from __future__ import annotations

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from .cli import (
    DetailPage,
    MenuActionResult,
    MenuItem,
    MenuScreen,
    _build_linear_detail_sections,
    _show_in_scrollable_screen,
    _stack_renderables,
)


def _build_rag_warmup_summary_panel():
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


def _build_rag_warmup_table():
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


def _current_warmup_mode_label() -> str:
    from mmcp.infrastructure.environment.config import get_config

    return get_config().rag_warmup_mode.strip().title()


def _warmup_status_lines() -> list[str]:
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
    return _build_linear_detail_sections([("Warmup Status", _warmup_status_lines())], width)


def _build_warmup_modes_detail_page(width: int):
    return _build_linear_detail_sections([("Warmup Modes", _warmup_modes_lines())], width)


def _render_rag_warmup_interactive_selector():
    return Group(_build_rag_warmup_summary_panel(), Text(""), _build_rag_warmup_table())


def _build_warmup_status_content():
    return _stack_renderables(_build_rag_warmup_summary_panel(), _build_rag_warmup_table())


def _build_warmup_status_pages() -> list[DetailPage]:
    return [
        DetailPage(title="Status", renderable_builder=_build_warmup_status_detail_page),
        DetailPage(title="Modes", renderable_builder=_build_warmup_modes_detail_page),
    ]


def _build_detail_screen(title: str, subtitle: str, content_builder):
    return MenuScreen(
        title=title, subtitle=subtitle, items=[], help_text="←: back • q: quit", content_builder=content_builder
    )


def _build_paged_detail_screen(title: str, subtitle: str, content_pages_builder):
    return MenuScreen(
        title=title,
        subtitle=subtitle,
        items=[],
        help_text="↑/↓: scroll • PgUp/PgDn: page • ←: back • q: quit",
        content_pages_builder=content_pages_builder,
    )


def set_rag_warmup_mode(mode: str) -> str:
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
    from mmcp.infrastructure.environment.config import get_config

    current_mode = get_config().rag_warmup_mode
    path = set_rag_warmup_mode(mode)

    if current_mode == mode:
        return f"[bold]Warmup mode:[/] [green]{mode}[/]\n[dim]Already active. Config remains at {path}[/]"
    return f"[bold]Warmup mode updated:[/] [yellow]{current_mode}[/] → [green]{mode}[/]\n[dim]Saved in {path}[/]"


def _set_warmup_mode_and_return(mode: str) -> MenuActionResult:
    return MenuActionResult(back_levels=1, notice=_show_saved_warmup_mode(mode))


def _prewarm_rag_now_and_return() -> MenuActionResult:
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
    from .upgrade import do_upgrade

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


def prewarm_rag_now_cli():
    import mmcp.presentation.cli.cli as cli_module
    from mmcp.presentation.mcp.server import prewarm_rag_now

    result = prewarm_rag_now()
    cli_module.CONSOLE.print(
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
    import mmcp.presentation.cli.cli as cli_module

    cli_module._show_stateful_menu(cli_module._build_warmup_menu())


def do_rag_warmup_command(args: list[str]):
    import mmcp.presentation.cli.cli as cli_module

    if not args or args[0] in {"show", "status"}:
        cli_module.show_rag_warmup_info()
        return

    if args[0] == "set":
        if len(args) < 2:
            raise SystemExit("Usage: context-life warmup set <lazy|startup|manual>")
        try:
            message = cli_module._show_saved_warmup_mode(args[1])
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        cli_module.CONSOLE.print(Panel(message, title="⚙️ Warmup Updated", border_style="green", box=box.ROUNDED))
        cli_module.show_rag_warmup_info()
        return

    if args[0] == "prewarm":
        cli_module.prewarm_rag_now_cli()
        return

    if args[0] in {"interactive", "selector", "select"}:
        cli_module.run_rag_warmup_interactive()
        return

    raise SystemExit("Usage: context-life warmup [show|set <mode>|prewarm|interactive]")


def show_rag_warmup_info():
    _show_in_scrollable_screen(_build_warmup_status_content(), title="RAG Warmup")
