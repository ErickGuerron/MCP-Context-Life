"""ANSI escape sequence handling for the CLI UI layer."""

from __future__ import annotations

import re
from io import StringIO

from rich.console import Console


def _render_renderable_to_lines(renderable, width: int) -> list[str]:
    """Pre-render a Rich renderable into ANSI-safe lines."""
    temp_buffer = StringIO()
    temp_console = Console(file=temp_buffer, width=width, force_terminal=True)
    temp_console.print(renderable)
    lines = temp_buffer.getvalue().split("\n")
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def _strip_ansi_len(s: str) -> int:
    """Estimate visible length by stripping ANSI escape sequences."""
    return len(re.sub(r"\033\[[0-9;]*[a-zA-Z]", "", s))
