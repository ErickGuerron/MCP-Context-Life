import time

from rich.console import Console

from mmcp import cli
from mmcp.cli import (
    DetailPage,
    _build_doctor_content,
    _build_doctor_pages,
    _build_info_content,
    _build_info_pages,
    _build_main_tui_menu,
    _build_menu_panel,
    _build_metrics_menu,
    _build_rag_warmup_summary_panel,
    _build_rag_warmup_table,
    _build_telemetry_content,
    _build_telemetry_pages,
    _build_warmup_menu,
    _build_warmup_status_content,
    _build_warmup_status_pages,
    _get_detail_pages,
    _move_detail_page,
    _move_menu_selection,
    _resolve_detail_layout,
    _set_warmup_mode_and_return,
)
from mmcp.config import get_config
from mmcp.session_store import SessionStore, UsageEvent


def _render_text(renderable) -> str:
    console = Console(record=True, width=160)
    console.print(renderable)
    return console.export_text().lower()


def _render_lines(renderable, width: int) -> list[str]:
    console = Console(record=True, width=width)
    console.print(renderable)
    return console.export_text().splitlines()


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
    assert "first use" in text
    assert "resources" in text


def test_warmup_menu_contains_integrated_actions():
    warmup_menu = _build_warmup_menu()

    labels = [item.label for item in warmup_menu.items]

    assert warmup_menu.title == "Config / Warmup"
    assert labels == ["Show warmup status", "Set Lazy", "Set Startup", "Set Manual", "Prewarm now"]
    assert warmup_menu.items[0].submenu is not None


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

    assert result.back_levels == 1
    assert "warmup mode updated" in result.notice.lower()
    assert "startup" in result.notice.lower()
    assert get_config().rag_warmup_mode == "startup"
    assert "rag warmup: startup" in text


def test_set_warmup_mode_action_returns_inline_notice_without_printing(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "manual"

    result = _set_warmup_mode_and_return("lazy")

    assert result.back_levels == 1
    assert "warmup mode updated" in result.notice.lower()
    assert "saved in" in result.notice.lower()


def test_metrics_menu_groups_status_and_diagnostics():
    metrics_menu = _build_metrics_menu()

    assert [item.label for item in metrics_menu.items] == ["Info", "Health", "Telemetry"]
    assert all(item.submenu is not None for item in metrics_menu.items)
    assert metrics_menu.items[0].submenu.content_pages_builder is not None
    assert metrics_menu.items[1].submenu.content_pages_builder is not None
    assert metrics_menu.items[2].submenu.content_builder is not None


def test_move_menu_selection_clamps_at_bounds():
    menu = _build_metrics_menu()

    _move_menu_selection(menu, -1)
    assert menu.selected == 0

    _move_menu_selection(menu, 10)
    assert menu.selected == len(menu.items) - 1


def test_show_saved_warmup_mode_updates_config(isolated_data_dir):
    cfg = get_config()
    cfg.rag_warmup_mode = "lazy"

    message = cli._show_saved_warmup_mode("startup")

    assert get_config().rag_warmup_mode == "startup"
    assert "warmup mode updated" in message.lower()


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


def test_compact_info_layout_avoids_wide_tables(isolated_data_dir):
    text = _render_text(_build_info_content())

    assert "🖥 system" in text
    assert "⚙️ config" in text
    assert "📦 dependencies" in text
    assert "property" not in text
    assert "available tools" not in text


def test_compact_health_layout_groups_checks_by_section(isolated_data_dir):
    text = _render_text(_build_doctor_content())

    assert "health summary" in text
    assert "runtime" in text
    assert "dependencies" in text
    assert "storage" in text
    assert "diagnostic results" not in text


def test_compact_telemetry_layout_uses_summary_and_model_usage(isolated_data_dir):
    text = _render_text(_build_telemetry_content())

    assert "💰 telemetry" in text
    assert "📅 budget reference" in text
    assert "model usage" in text
    assert "weekly usage tracker" not in text


def test_compact_warmup_status_layout_uses_panels(isolated_data_dir):
    text = _render_text(_build_warmup_status_content())

    assert "rag warmup status" in text
    assert "warmup modes" in text
    assert "interactive warmup selector" not in text


def test_paged_dense_views_expose_multiple_compact_pages(isolated_data_dir):
    assert [page.title for page in _build_info_pages()] == ["Overview", "Warmup", "Runtime Surface"]
    assert [page.title for page in _build_doctor_pages()] == ["Summary", "Warmup", "Checks", "Storage + Paths"]
    assert [page.title for page in _build_telemetry_pages()] == ["Overview", "Model Usage"]
    assert [page.title for page in _build_warmup_status_pages()] == ["Status", "Modes"]


def test_dense_detail_footer_mentions_left_right_navigation(isolated_data_dir):
    info_screen = _build_metrics_menu().items[0].submenu

    text = _render_text(_build_menu_panel(info_screen, "Main Menu  ›  Metrics  ›  Info"))

    assert "page: ←/→" in text
    assert "page 1/3" in text


def test_move_detail_page_clamps_and_resets_scroll():
    screen = cli.MenuScreen(
        title="Dense",
        subtitle="",
        items=[],
        content_pages_builder=lambda: [
            DetailPage("One", lambda: "one"),
            DetailPage("Two", lambda: "two"),
        ],
        page_index=0,
        scroll_offset=7,
    )

    _move_detail_page(screen, 1, 2)
    assert screen.page_index == 1
    assert screen.scroll_offset == 0

    _move_detail_page(screen, 5, 2)
    assert screen.page_index == 1


def test_warmup_detail_screen_uses_paged_navigation():
    warmup_status = _build_warmup_menu().items[0].submenu

    assert warmup_status.title == "RAG Warmup Status"
    assert warmup_status.content_pages_builder is not None
    assert len(warmup_status.content_pages_builder()) == 2


def test_health_summary_page_fits_without_cutting_panel_borders(isolated_data_dir, monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=76, height=28))

    try:
        health_screen = _build_metrics_menu().items[1].submenu
        text = _render_text(_build_menu_panel(health_screen, "Main Menu  ›  Metrics  ›  Health"))
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    assert "health summary" in text
    assert "all checks passed" in text
    assert "page 1/4" in text


def test_warmup_detail_screen_drops_nested_outer_panel_to_avoid_border_clipping(isolated_data_dir, monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=76, height=28))

    try:
        warmup_screen = _build_warmup_menu().items[0].submenu
        text = _render_text(_build_menu_panel(warmup_screen, "Main Menu  ›  Config  ›  Warmup"))
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    assert "interactive warmup selector" not in text
    assert "page 1/2" in text
    assert "warmup status" in text
    assert "warmup modes" not in text


def test_short_detail_pages_shrink_to_content_height(monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=100, height=40))

    try:
        screen = cli.MenuScreen(
            title="Dense",
            subtitle="",
            items=[],
            content_pages_builder=lambda: [DetailPage("Summary", lambda: cli.Panel("short", title="Inner"))],
        )
        layout = _resolve_detail_layout(screen, "Main Menu  ›  Dense")
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    assert layout["body_height"] < 10
    assert layout["max_offset"] == 0


def test_internal_divider_fills_available_width_without_manual_side_walls():
    divider = cli._build_internal_divider("Config", 32)

    plain = divider.plain

    assert len(plain) == 32
    assert " Config " in plain
    assert "|" not in plain


def test_paged_info_view_uses_single_main_container_and_internal_dividers(monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=76, height=40))

    try:
        info_screen = _build_metrics_menu().items[0].submenu
        layout = _resolve_detail_layout(info_screen, "Main Menu  ›  Metrics  ›  Info")
        lines = layout["page_lines"]
        rendered_lines = _render_lines(_build_menu_panel(info_screen, "Main Menu  ›  Metrics  ›  Info"), width=76)
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    joined = "\n".join(lines).lower()
    rendered_joined = "\n".join(rendered_lines).lower()

    assert any("system" in line.lower() and "─" in line for line in lines)
    assert any("config" in line.lower() and "─" in line for line in lines)
    assert "🖥 system" not in joined
    assert all(len(line) <= 76 for line in rendered_lines)
    assert "|" not in rendered_joined


def test_health_view_keeps_dividers_inside_single_container_on_narrow_terminal(isolated_data_dir, monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=76, height=28))

    try:
        health_screen = _build_metrics_menu().items[1].submenu
        lines = _render_lines(_build_menu_panel(health_screen, "Main Menu  ›  Metrics  ›  Health"), width=76)
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    joined = "\n".join(lines).lower()

    assert any("health summary" in line.lower() and "─" in line for line in lines)
    assert "all checks passed" in joined
    assert "page 1/4" in joined
    assert all(len(line) <= 76 for line in lines)
    assert "|" not in joined


def test_detail_pages_builder_is_cached_per_screen_instance():
    calls = []

    screen = cli.MenuScreen(
        title="Dense",
        subtitle="",
        items=[],
        content_pages_builder=lambda: calls.append("build") or [DetailPage("One", lambda: "one")],
    )

    assert len(_get_detail_pages(screen)) == 1
    assert len(_get_detail_pages(screen)) == 1
    assert calls == ["build"]


def test_detail_lines_are_cached_between_renders(monkeypatch):
    original_console = cli.CONSOLE
    monkeypatch.setattr(cli, "CONSOLE", Console(width=100, height=32))

    render_calls = []
    screen = cli.MenuScreen(
        title="Dense",
        subtitle="",
        items=[],
        content_pages_builder=lambda: [
            DetailPage("One", lambda: render_calls.append("render") or cli.Panel("cached", title="Panel"))
        ],
    )

    try:
        _build_menu_panel(screen, "Main Menu  ›  Dense")
        screen.scroll_offset = 1
        _build_menu_panel(screen, "Main Menu  ›  Dense")
    finally:
        monkeypatch.setattr(cli, "CONSOLE", original_console)

    assert render_calls == ["render"]


def test_telemetry_screen_keeps_summary_and_usage_in_same_scroll_view():
    telemetry_screen = _build_metrics_menu().items[2].submenu

    assert telemetry_screen.content_builder is not None
    assert telemetry_screen.content_pages_builder is None


def test_long_telemetry_rows_wrap_without_exceeding_console_width(isolated_data_dir):
    store = SessionStore(get_config().resolve_cache_db_path())
    store.record_usage(
        UsageEvent(
            session_id="s-1",
            model_name="openai/super-long-model-name-with-many-segments-and-a-very-long-suffix-for-layout-tests",
            input_tokens=120_000,
            output_tokens=45_000,
            effective_saved_tokens=30_000,
        )
    )

    console = Console(record=True, width=72)
    console.print(_build_telemetry_content())
    lines = console.export_text().splitlines()

    assert any("super-long-model-name" in line for line in lines)
    assert max(len(line) for line in lines) <= 72


def test_telemetry_dashboard_uses_explicit_accounting_labels(isolated_data_dir):
    store = SessionStore(get_config().resolve_cache_db_path())
    store.record_usage(
        UsageEvent(
            session_id="s-2",
            model_name="openai/gpt-5.4",
            input_tokens=4_321,
            output_tokens=250,
            effective_saved_tokens=600,
        )
    )

    text = _render_text(_build_telemetry_content())

    assert "accounted input" in text
    assert "saved / reused" in text
    assert "default request budget" in text
    assert "mcp tool calls only" in text
    assert "per-model budget" not in text


def test_telemetry_dashboard_overview_uses_rolling_week_window(isolated_data_dir):
    store = SessionStore(get_config().resolve_cache_db_path())
    store.record_usage(
        UsageEvent(
            session_id="old-event",
            model_name="openai/gpt-4.1",
            input_tokens=9_999,
            output_tokens=111,
            effective_saved_tokens=222,
            timestamp=time.time() - (8 * 24 * 60 * 60),
        )
    )
    store.record_usage(
        UsageEvent(
            session_id="recent-event",
            model_name="openai/gpt-5.4",
            input_tokens=321,
            output_tokens=45,
            effective_saved_tokens=67,
            timestamp=time.time(),
        )
    )

    text = _render_text(_build_telemetry_content())

    assert "accounted input" in text
    assert "321" in text
    assert "saved / reused" in text
    assert "67" in text
    assert "10.1k" not in text


def test_session_store_exposes_explicit_and_legacy_usage_fields(isolated_data_dir):
    store = SessionStore(get_config().resolve_cache_db_path())
    store.record_usage(
        UsageEvent(
            session_id="s-3",
            model_name="openai/gpt-5.4",
            input_tokens=100,
            output_tokens=40,
            cached_input_tokens=15,
            uncached_input_tokens=85,
            effective_saved_tokens=15,
        )
    )

    weekly = store.get_weekly_usage()["openai/gpt-5.4"]
    totals = store.get_all_time_stats()

    assert weekly["accounted_input_tokens"] == 100
    assert weekly["output_tokens"] == 40
    assert weekly["saved_tokens"] == 15
    assert weekly["cached_input_tokens"] == 15
    assert weekly["live_input_tokens"] == 85
    assert weekly["activity_tokens"] == 140
    assert weekly["used"] == 140
    assert weekly["saved"] == 15
    assert totals["accounted_input_tokens"] == 100
    assert totals["activity_tokens"] == 140
