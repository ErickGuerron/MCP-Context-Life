from rich.console import Console

from mmcp import cli
from mmcp.cli import (
    MenuActionResult,
    _build_main_tui_menu,
    _build_menu_panel,
    _build_metrics_menu,
    _build_rag_warmup_interactive_actions_panel,
    _build_rag_warmup_summary_panel,
    _build_rag_warmup_table,
    _build_warmup_menu,
    _move_menu_selection,
    _set_warmup_mode_and_return,
)
from mmcp.config import get_config


def _render_text(renderable) -> str:
    console = Console(record=True, width=160)
    console.print(renderable)
    return console.export_text().lower()


def test_rag_warmup_summary_panel_explains_current_mode(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "manual"

    text = _render_text(_build_rag_warmup_summary_panel())

    assert "current mode:" in text
    assert "manual" in text
    assert "context-life warmup set" in text
    assert "context-life prewarm" in text


def test_rag_warmup_table_lists_all_modes(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "lazy"

    text = _render_text(_build_rag_warmup_table())

    assert "lazy (default)" in text
    assert "startup" in text
    assert "manual" in text
    assert "first rag search/index" in text


def test_rag_warmup_interactive_actions_panel_lists_selector_actions():
    text = _render_text(_build_rag_warmup_interactive_actions_panel())

    assert "interactive warmup selector" in text
    assert "j / ↓" in text
    assert "k / ↑" in text
    assert "enter" in text
    assert "esc" in text
    assert "q" in text


def test_warmup_menu_contains_integrated_actions():
    warmup_menu = _build_warmup_menu()

    labels = [item.label for item in warmup_menu.items]

    assert warmup_menu.title == "Config / Warmup"
    assert labels == ["Show warmup status", "Set Lazy", "Set Startup", "Set Manual", "Prewarm now"]


def test_main_menu_is_split_into_config_and_metrics():
    main_menu = _build_main_tui_menu()

    assert [item.label for item in main_menu.items] == ["Config", "Metrics"]
    assert main_menu.items[0].submenu is not None
    assert main_menu.items[1].submenu is not None


def test_config_menu_shows_current_warmup_mode_inline(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "startup"

    config_menu = cli._build_config_menu()
    text = _render_text(_build_menu_panel(config_menu, "Main Menu  ›  Config"))

    assert "rag warmup: startup" in text


def test_set_warmup_mode_action_returns_to_config_and_updates_inline_label(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "lazy"

    result = _set_warmup_mode_and_return("startup")
    config_menu = cli._build_config_menu()
    text = _render_text(_build_menu_panel(config_menu, "Main Menu  ›  Config"))

    assert result == MenuActionResult(back_levels=1)
    assert get_config().rag_warmup_mode == "startup"
    assert "rag warmup: startup" in text


def test_metrics_menu_groups_status_and_diagnostics():
    metrics_menu = _build_metrics_menu()

    assert [item.label for item in metrics_menu.items] == ["Info", "Health", "Telemetry"]


def test_move_menu_selection_clamps_at_bounds():
    menu = _build_metrics_menu()

    _move_menu_selection(menu, -1)
    assert menu.selected == 0

    _move_menu_selection(menu, 10)
    assert menu.selected == len(menu.items) - 1


def test_show_saved_warmup_mode_updates_config(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "lazy"

    cli._show_saved_warmup_mode("startup")

    assert get_config().rag_warmup_mode == "startup"


def test_do_rag_warmup_command_dispatches_interactive(monkeypatch):
    called = []
    monkeypatch.setattr(cli, "run_rag_warmup_interactive", lambda: called.append("interactive"))

    cli.do_rag_warmup_command(["interactive"])

    assert called == ["interactive"]


def test_run_rag_warmup_interactive_requires_tty(monkeypatch):
    monkeypatch.setattr(cli.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: False)

    try:
        cli.run_rag_warmup_interactive()
    except SystemExit as exc:
        assert "requires a tty" in str(exc).lower()
    else:
        raise AssertionError("Expected SystemExit when no TTY is available")
