from pathlib import Path


def _module_folder_name(module) -> str:
    return Path(module.__file__).parent.name


def test_infrastructure_layer_modules_are_visible_and_canonical():
    import mmcp.infrastructure.context.trim_history as context_trim_history
    import mmcp.infrastructure.environment.config as environment_config
    import mmcp.infrastructure.environment.orchestrator_detector as orchestrator_detector
    import mmcp.infrastructure.persistence.session_store as persistence_session_store
    import mmcp.infrastructure.tokens.token_counter as token_counter

    assert _module_folder_name(environment_config) == "environment"
    assert _module_folder_name(orchestrator_detector) == "environment"
    assert _module_folder_name(persistence_session_store) == "persistence"
    assert _module_folder_name(token_counter) == "tokens"
    assert _module_folder_name(context_trim_history) == "context"


def test_legacy_root_shim_files_are_removed():
    repo_root = Path(__file__).resolve().parents[1]
    legacy_files = [
        repo_root / "mmcp" / "app_container.py",
        repo_root / "mmcp" / "cli.py",
        repo_root / "mmcp" / "server.py",
        repo_root / "mmcp" / "cache_manager.py",
        repo_root / "mmcp" / "config.py",
        repo_root / "mmcp" / "orchestrator_detector.py",
        repo_root / "mmcp" / "rag_engine.py",
        repo_root / "mmcp" / "session_store.py",
        repo_root / "mmcp" / "telemetry_service.py",
        repo_root / "mmcp" / "token_counter.py",
        repo_root / "mmcp" / "trim_history.py",
        repo_root / "mmcp" / "infrastructure" / "cache_manager.py",
        repo_root / "mmcp" / "infrastructure" / "config.py",
        repo_root / "mmcp" / "infrastructure" / "orchestrator_detector.py",
        repo_root / "mmcp" / "infrastructure" / "rag_engine.py",
        repo_root / "mmcp" / "infrastructure" / "session_store.py",
        repo_root / "mmcp" / "infrastructure" / "telemetry_service.py",
        repo_root / "mmcp" / "infrastructure" / "token_counter.py",
        repo_root / "mmcp" / "infrastructure" / "trim_history.py",
        repo_root / "mmcp" / "presentation" / "server.py",
        repo_root / "mmcp" / "presentation" / "__main__.py",
    ]

    assert all(not path.exists() for path in legacy_files)


def test_package_entrypoint_imports_canonical_presentation_modules():
    repo_root = Path(__file__).resolve().parents[1]
    entrypoint_source = (repo_root / "mmcp" / "__main__.py").read_text(encoding="utf-8")

    assert "from mmcp.presentation import __main__ as _impl" not in entrypoint_source
    assert "from mmcp.presentation.mcp.server import" in entrypoint_source
    assert "from mmcp.presentation.cli" in entrypoint_source


def test_presentation_layer_modules_are_visible_and_canonical():
    import mmcp.presentation.app_container as presentation_app_container
    import mmcp.presentation.cli as presentation_cli
    import mmcp.presentation.cli.upgrade as presentation_upgrade_impl
    import mmcp.presentation.mcp.server as presentation_server_impl

    assert _module_folder_name(presentation_app_container) == "presentation"
    assert _module_folder_name(presentation_cli) == "cli"
    assert presentation_cli.do_upgrade is presentation_upgrade_impl.do_upgrade
    assert presentation_server_impl.mcp is not None
