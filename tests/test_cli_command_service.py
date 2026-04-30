import pytest

from mmcp.application.features.cli.commands import (
    CliCommandError,
    UpgradeCommandRequest,
    WarmupCommandRequest,
    parse_upgrade_args,
    parse_warmup_args,
)


def test_parse_warmup_args_defaults_to_show_status():
    assert parse_warmup_args([]) == WarmupCommandRequest(action="show")
    assert parse_warmup_args(["status"]) == WarmupCommandRequest(action="show")


def test_parse_warmup_args_parses_set_and_requires_mode():
    assert parse_warmup_args(["set", "startup"]) == WarmupCommandRequest(action="set", mode="startup")

    with pytest.raises(CliCommandError, match="context-life warmup set"):
        parse_warmup_args(["set"])


def test_parse_warmup_args_recognizes_other_actions():
    assert parse_warmup_args(["prewarm"]) == WarmupCommandRequest(action="prewarm")
    assert parse_warmup_args(["interactive"]) == WarmupCommandRequest(action="interactive")
    assert parse_warmup_args(["selector"]) == WarmupCommandRequest(action="interactive")


def test_parse_upgrade_args_extracts_flags_from_argv():
    assert parse_upgrade_args([]) == UpgradeCommandRequest()
    assert parse_upgrade_args(["--dry-run"]) == UpgradeCommandRequest(dry_run=True)
    assert parse_upgrade_args(["--version", "v1.2.3", "--dry-run"]) == UpgradeCommandRequest(
        target_version="v1.2.3",
        dry_run=True,
    )
