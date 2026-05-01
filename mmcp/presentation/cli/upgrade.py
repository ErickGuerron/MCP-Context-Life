from __future__ import annotations

import subprocess
import sys
from typing import Callable

from rich import box
from rich.align import Align
from rich.panel import Panel

from .cli import CONSOLE, GITHUB_REPO, REPO_URL, _fetch_latest_release, get_version, print_banner


def _enter_alt_screen_if_tty() -> tuple[Callable[[], int], Callable[[], object]] | None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None

    write = sys.stdout.write
    flush = sys.stdout.flush
    write("\033[?1049h\033[?25l\033[2J\033[H")
    flush()
    return write, flush


def _exit_alt_screen(session: tuple[Callable[[], int], Callable[[], object]] | None) -> None:
    if session is None:
        return

    write, flush = session
    write("\033[?25h\033[?1049l")
    flush()


def do_upgrade(target_version: str | None = None, dry_run: bool = False):
    session = _enter_alt_screen_if_tty()
    try:
        print_banner()

        old_version = get_version()

        if target_version:
            tag = target_version.lstrip("v")
            release_url = f"https://github.com/{GITHUB_REPO}/releases/tag/v{tag}"
        else:
            with CONSOLE.status("[bold cyan]Checking for latest release...[/]", spinner="dots"):
                tag, release_url = _fetch_latest_release()

        if not tag:
            CONSOLE.print("\n  [bold yellow]⚠ Could not fetch release info from GitHub[/]")
            CONSOLE.print("  [dim]Falling back to latest from repository...[/]\n")
            tag = None
            install_target = f"git+{REPO_URL}"
        else:
            install_target = f"git+{REPO_URL}@v{tag}"

        CONSOLE.print(
            Align.center(
                Panel(
                    f"[bold]Current version:[/] [yellow]v{old_version}[/]\n"
                    f"[bold]Target version:[/]  [green]v{tag or 'latest'}[/]" + (f"\n[dim]{release_url}[/]" if release_url else ""),
                    title="🔄 Context-Life Upgrade",
                    border_style="yellow",
                    box=box.ROUNDED,
                )
            )
        )

        if tag and tag == old_version:
            CONSOLE.print(f"\n  [bold green]✓ Already up to date[/] [dim](v{old_version})[/]\n")
            return

        if dry_run:
            CONSOLE.print(f"\n  [bold cyan]ℹ Dry run:[/] would install [green]v{tag or 'latest'}[/]")
            CONSOLE.print(f"  [dim]pip install --upgrade {install_target}[/]\n")
            return

        with CONSOLE.status("[bold cyan]Downloading and installing...[/]", spinner="dots"):
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", install_target], capture_output=True, text=True
            )

        if result.returncode == 0:
            new_version = get_version()
            if new_version != old_version:
                CONSOLE.print(f"\n  [bold green]✓ Upgraded![/] [yellow]v{old_version}[/] → [green]v{new_version}[/]\n")
            else:
                CONSOLE.print(f"\n  [bold green]✓ Already up to date[/] [dim](v{new_version})[/]\n")
            for line in result.stdout.strip().split("\n")[-5:]:
                if line:
                    CONSOLE.print(f"  [dim]{line}[/]")
        else:
            CONSOLE.print("\n  [bold red]✗ Upgrade failed[/]\n")
            CONSOLE.print(f"  [red]{result.stderr.strip()[:500]}[/]")
            sys.exit(1)
    finally:
        _exit_alt_screen(session)
