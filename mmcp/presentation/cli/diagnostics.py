from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from .cli import (
    DetailPage,
    MenuItem,
    MenuScreen,
    _build_linear_detail_sections,
    _compact_list_panel,
    _compact_panel,
    _detail_section_lines,
    _fetch_latest_release,
    _safe_import_check,
    _show_in_scrollable_screen,
    _stack_renderables,
    format_big_number,
    get_version,
)
from .warmup import (
    _build_detail_screen,
    _build_paged_detail_screen,
    _build_rag_warmup_summary_panel,
    _build_warmup_status_detail_page,
)


def _build_info_content():
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
                        [
                            f"[bold]Version:[/] v{get_version()}",
                            f"[bold]Python:[/] {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                            f"[bold]OS:[/] {platform.system()}",
                            f"[bold]Arch:[/] {platform.machine()}",
                        ],
                    ),
                    (
                        "⚙️ Config",
                        [
                            f"[bold]Config file:[/] {str(_default_config_path())}",
                            f"[bold]Data dir:[/] {str(cfg.resolve_data_dir())}",
                            f"[bold]RAG DB:[/] {cfg.resolve_rag_db_path()}",
                            f"[bold]Warmup:[/] {cfg.rag_warmup_mode}",
                            f"[bold]Top K / Score:[/] {cfg.rag_top_k} / {cfg.rag_min_score}",
                            f"[bold]Token budget:[/] {cfg.token_budget_default:,}",
                        ],
                    ),
                ],
                width,
            ),
        ),
        DetailPage(title="Warmup", renderable_builder=_build_warmup_status_detail_page),
        DetailPage(
            title="Runtime Surface",
            renderable_builder=lambda width: _build_linear_detail_sections(
                [("📦 Dependencies", dependency_lines), ("⚡ Tools", tool_lines), ("📊 Resources", resource_lines)],
                width,
            ),
        ),
    ]


def show_info():
    _show_in_scrollable_screen(_build_info_content(), title="System Info")


def _build_doctor_content():
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
    checks.append(("Config file", "✅" if cfg_exists else "ℹ️", f"{cfg_path}" + (" (using defaults)" if not cfg_exists else "")))

    cfg = get_config()
    data_dir = cfg.resolve_data_dir()
    checks.append(("Data directory", "✅", str(data_dir)))

    rag_path = Path(cfg.resolve_rag_db_path())
    rag_writable = os.access(rag_path.parent, os.W_OK) if rag_path.parent.exists() else False
    checks.append(("LanceDB path", "✅" if rag_writable else "⚠️", f"{rag_path}" + (" (not writable)" if not rag_writable else "")))

    warmup = get_rag_warmup_mode_details(cfg.rag_warmup_mode)
    checks.append(("RAG warmup mode", "✅", f"{cfg.rag_warmup_mode} — {warmup['current']['startup_impact']}"))

    model_cache = Path.home() / ".cache" / "huggingface"
    if os.name == "nt":
        model_cache = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "huggingface"
    cache_exists = model_cache.exists()
    checks.append(("Model cache", "✅" if cache_exists else "ℹ️", f"{model_cache}" + (" (will download on first use)" if not cache_exists else "")))

    try:
        latest_tag, _ = _fetch_latest_release()
    except Exception:
        latest_tag = None

    if latest_tag:
        is_latest = latest_tag == ver
        checks.append(("Latest release", "✅" if is_latest else "⬆️", f"v{latest_tag}" + ("" if is_latest else f" (you have v{ver})")))
    else:
        checks.append(("Latest release", "⚠️", "Could not reach GitHub API"))

    has_errors = any(s == "❌" for _, s, _ in checks)
    summary_panel = _compact_panel(
        "🩺 Health Summary",
        [
            (
                "Status",
                "[bold red]Some checks failed.[/] Fix the red items and run again."
                if has_errors
                else "[bold green]All checks passed.[/] Context-Life is ready to use.",
            )
        ],
        border_style="red" if has_errors else "green",
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
    checks.append(("Config file", "✅" if cfg_exists else "ℹ️", f"{cfg_path}" + (" (using defaults)" if not cfg_exists else "")))

    cfg = get_config()
    data_dir = cfg.resolve_data_dir()
    checks.append(("Data directory", "✅", str(data_dir)))

    rag_path = Path(cfg.resolve_rag_db_path())
    rag_writable = os.access(rag_path.parent, os.W_OK) if rag_path.parent.exists() else False
    checks.append(("LanceDB path", "✅" if rag_writable else "⚠️", f"{rag_path}" + (" (not writable)" if not rag_writable else "")))

    warmup = get_rag_warmup_mode_details(cfg.rag_warmup_mode)
    checks.append(("RAG warmup mode", "✅", f"{cfg.rag_warmup_mode} — {warmup['current']['startup_impact']}"))

    model_cache = Path.home() / ".cache" / "huggingface"
    if os.name == "nt":
        model_cache = Path(os.environ.get("USERPROFILE", Path.home())) / ".cache" / "huggingface"
    cache_exists = model_cache.exists()
    checks.append(("Model cache", "✅" if cache_exists else "ℹ️", f"{model_cache}" + (" (will download on first use)" if not cache_exists else "")))

    try:
        latest_tag, _ = _fetch_latest_release()
    except Exception:
        latest_tag = None

    if latest_tag:
        is_latest = latest_tag == ver
        checks.append(("Latest release", "✅" if is_latest else "⬆️", f"v{latest_tag}" + ("" if is_latest else f" (you have v{ver})")))
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
                [("Health Summary", ["[bold red]Some checks failed.[/] Fix the red items and run again." if has_errors else "[bold green]All checks passed.[/] Context-Life is ready to use."])],
                width,
            ),
        ),
        DetailPage(title="Warmup", renderable_builder=_build_warmup_status_detail_page),
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
    _show_in_scrollable_screen(_build_doctor_content(), title="Diagnostics")


def _build_telemetry_content():
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
                f"[bold]{model_name}[/] — input {format_big_number(used)} • output {format_big_number(transformed)} • saved {format_big_number(saved)}"
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
            [("Window", "Rolling 7 days"), ("Default request budget", format_big_number(budget)), ("Tracked models", str(len(weekly)))],
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
                f"[bold]{model_name}[/] — input {format_big_number(used)} • output {format_big_number(transformed)} • saved {format_big_number(saved)}"
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
                    [("Window", "Rolling 7 days"), ("Default request budget", format_big_number(budget)), ("Tracked models", str(len(weekly)))],
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
    _show_in_scrollable_screen(_build_telemetry_content(), title="Telemetry Dashboard")


def _build_metrics_menu() -> MenuScreen:
    return MenuScreen(
        title="Metrics",
        subtitle="Status, diagnostics, and runtime visibility for the current environment.",
        items=[
            MenuItem("Info", "System, config, dependencies, tools, and resources overview.", submenu=_build_paged_detail_screen("Info", "Compact system pages with horizontal navigation for dense sections.", _build_info_pages)),
            MenuItem("Health", "Environment diagnostics and readiness checks.", submenu=_build_paged_detail_screen("Health", "Readiness checks grouped into compact horizontally navigable pages.", _build_doctor_pages)),
            MenuItem("Telemetry", "Weekly usage, savings, and budget tracking dashboard.", submenu=_build_detail_screen("Telemetry", "Scrollable telemetry dashboard with summary and model usage kept together.", _build_telemetry_content)),
        ],
    )
