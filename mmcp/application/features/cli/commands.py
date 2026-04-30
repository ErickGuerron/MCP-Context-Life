from __future__ import annotations

from dataclasses import dataclass


class CliCommandError(ValueError):
    """Invalid CLI command usage."""


@dataclass(frozen=True, slots=True)
class WarmupCommandRequest:
    action: str
    mode: str | None = None


@dataclass(frozen=True, slots=True)
class UpgradeCommandRequest:
    target_version: str | None = None
    dry_run: bool = False


def parse_warmup_args(args: list[str]) -> WarmupCommandRequest:
    if not args or args[0] in {"show", "status"}:
        return WarmupCommandRequest(action="show")

    command = args[0]
    if command == "set":
        if len(args) < 2:
            raise CliCommandError("Usage: context-life warmup set <lazy|startup|manual>")
        return WarmupCommandRequest(action="set", mode=args[1])

    if command == "prewarm":
        return WarmupCommandRequest(action="prewarm")

    if command in {"interactive", "selector", "select"}:
        return WarmupCommandRequest(action="interactive")

    raise CliCommandError("Usage: context-life warmup [show|set <mode>|prewarm|interactive]")


def parse_upgrade_args(args: list[str]) -> UpgradeCommandRequest:
    target_version = None
    dry_run = "--dry-run" in args

    if "--version" in args:
        idx = args.index("--version")
        if idx + 1 < len(args):
            target_version = args[idx + 1]

    return UpgradeCommandRequest(target_version=target_version, dry_run=dry_run)
