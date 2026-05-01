from __future__ import annotations

import os
import subprocess
import sys

from rich import box
from rich.align import Align
from rich.panel import Panel

from .cli import CONSOLE, GITHUB_REPO, REPO_URL, _fetch_latest_release, _read_tui_key, get_version


def _clear_screen() -> None:
    if sys.stdout.isatty():
        if os.name == "nt":
            os.system("cls")
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def _enter_alt_screen() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[?1049h\033[?25l\033[2J\033[H")
        sys.stdout.flush()


def _exit_alt_screen() -> None:
    if sys.stdout.isatty():
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()


def _restore_main_screen() -> None:
    _exit_alt_screen()
    _clear_screen()


def _wait_for_key(allow_retry: bool = False) -> str:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return "enter"

    while True:
        key = _read_tui_key()
        if key in {"enter", "esc", "q"}:
            return key
        if allow_retry and key == "right":
            return "enter"


def _build_confirmation_panel(
    old_version: str, target_label: str, release_url: str | None, same_version: bool
) -> Panel:
    lines = [
        f"[bold]¿Querés actualizar el MCP?[/]  context-life {old_version} -> {target_label}",
        "[dim]Enter: continue • Esc/q: cancel[/]",
        "[dim]This will upgrade the installed package and may replace the current runtime files.[/]",
    ]
    if release_url:
        lines.append(f"[dim]{release_url}[/]")
    if same_version:
        lines.append("[bold yellow]You are already on the latest release.[/]")
    return Panel("\n".join(lines), title="Context-Life Upgrade", border_style="cyan", box=box.ROUNDED)


def _build_success_panel(old_version: str, new_version: str) -> Panel:
    return Panel(
        f"[bold green]✓ Upgrade completed successfully.[/]\n"
        f"[bold]Version:[/] [yellow]v{old_version}[/] → [green]v{new_version}[/]\n\n"
        "[dim]Press Enter to return to the main screen. Press Esc/q to exit.[/]",
        title="Upgrade complete",
        border_style="green",
        box=box.ROUNDED,
    )


def _build_failure_panel(old_version: str, target_label: str, install_target: str, stderr_text: str | None) -> Panel:
    body = (
        f"[bold red]✗ Upgrade failed.[/]\n"
        f"[bold]Current:[/] [yellow]v{old_version}[/]\n"
        f"[bold]Target:[/] [green]{target_label}[/]\n\n"
        "[bold]Recommended:[/] install uv first, then retry with uv tool.\n"
        "[bold]Step 1:[/] python -m pip install uv\n"
        f'[bold]Step 2:[/] uv tool install --force "{install_target}"\n\n'
        "[dim]Enter: try again • Esc/q: cancel[/]"
    )
    if stderr_text:
        body += f"\n\n[red]{stderr_text[:500]}[/]"
    return Panel(body, title="Fallback with uv", border_style="yellow", box=box.ROUNDED)


def do_upgrade(target_version: str | None = None, dry_run: bool = False, inside_tui: bool = False):
    while True:
        old_version = get_version()

        if target_version:
            tag = target_version.lstrip("v")
            release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/v{tag}"
        else:
            tag, release_url = _fetch_latest_release()

        if not tag:
            install_target = f"git+{REPO_URL}"
            target_label = "latest"
        else:
            install_target = f"git+{REPO_URL}@v{tag}"
            target_label = f"v{tag}"

        same_version = bool(tag and tag == old_version)

        _clear_screen()
        CONSOLE.print(
            Align.center(
                _build_confirmation_panel(old_version, target_label, release_url, same_version=same_version),
                vertical="middle",
            )
        )

        if dry_run:
            CONSOLE.print(f"\n  [bold cyan]ℹ Dry run:[/] would install [green]{target_label}[/]")
            CONSOLE.print(f'  [dim]uv tool install --force "{install_target}"[/]\n')
            return

        if _wait_for_key() in {"esc", "q"}:
            _clear_screen()
            return

        if not inside_tui:
            _enter_alt_screen()

        if same_version:
            CONSOLE.print(Align.center(_build_success_panel(old_version, old_version), vertical="middle"))
            _wait_for_key()
            if inside_tui:
                _clear_screen()
            else:
                _restore_main_screen()
            return

        with CONSOLE.status("[bold cyan]Downloading and installing...[/]", spinner="dots"):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", install_target],
                capture_output=True,
                text=True,
            )

        if result.returncode == 0:
            new_version = get_version()
            CONSOLE.print(Align.center(_build_success_panel(old_version, new_version), vertical="middle"))
            _wait_for_key()
            if inside_tui:
                _clear_screen()
            else:
                _restore_main_screen()
            return

        failure_panel = _build_failure_panel(
            old_version,
            target_label,
            install_target,
            result.stderr.strip() or None,
        )
        CONSOLE.print(Align.center(failure_panel, vertical="middle"))
        if _wait_for_key(allow_retry=True) == "enter":
            if inside_tui:
                _clear_screen()
            else:
                _restore_main_screen()
            continue
        if inside_tui:
            _clear_screen()
        else:
            _restore_main_screen()
        return
