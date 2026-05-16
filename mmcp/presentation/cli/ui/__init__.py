"""UI layer: widgets, ANSI rendering, layout, and keyboard input."""

from .ansi import _render_renderable_to_lines, _strip_ansi_len
from .input import _read_scroll_key, _read_tui_key
from .render import (
    BANNER,
    CONSOLE,
    _build_internal_divider,
    _build_linear_detail_sections,
    _build_tui_header,
    _compact_list_panel,
    _compact_panel,
    _detail_body_width,
    _detail_footer_text,
    _detail_section_lines,
    _measure_renderable_height,
    _resolve_detail_layout,
    _stack_renderables,
    get_version,
)
from .telemetry_fmt import format_big_number
from .widgets import (
    _build_rag_warmup_summary_panel,
    _build_rag_warmup_table,
    _markup_pairs,
    _markup_text,
    _render_rag_warmup_interactive_selector,
    _warmup_modes_lines,
    _warmup_status_lines,
)

__all__ = [
    # ansi
    "_render_renderable_to_lines",
    "_strip_ansi_len",
    # input
    "_read_tui_key",
    "_read_scroll_key",
    # render
    "BANNER",
    "CONSOLE",
    "_build_internal_divider",
    "_build_linear_detail_sections",
    "_build_tui_header",
    "_compact_list_panel",
    "_compact_panel",
    "_detail_body_width",
    "_detail_footer_text",
    "_detail_section_lines",
    "_measure_renderable_height",
    "_resolve_detail_layout",
    "_stack_renderables",
    "format_big_number",
    "get_version",
    # widgets
    "_build_rag_warmup_summary_panel",
    "_build_rag_warmup_table",
    "_markup_pairs",
    "_markup_text",
    "_render_rag_warmup_interactive_selector",
    "_warmup_modes_lines",
    "_warmup_status_lines",
]
