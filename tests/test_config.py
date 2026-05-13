"""
Tests for OrchestratorFeaturesConfig and [orchestrator] TOML loading.
"""

from pathlib import Path

from mmcp.infrastructure.environment.config import (
    OrchestratorFeaturesConfig,
    load_config,
)


class TestAutoInvokeCacheConfig:
    """Test auto_invoke_cache feature flag and TTL config loading."""

    def test_load_config_auto_invoke_cache_enabled(self, tmp_path: Path):
        """Config should read auto_invoke_cache.enabled flag."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[auto_invoke_cache]\nenabled = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.auto_invoke_cache_enabled is True

    def test_load_config_auto_invoke_cache_disabled(self, tmp_path: Path):
        """Config should default to disabled when absent."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("", encoding="utf-8")

        cfg = load_config(str(config_path))

        assert cfg.auto_invoke_cache_enabled is False

    def test_load_config_auto_invoke_cache_ttl_seconds(self, tmp_path: Path):
        """Config should read auto_invoke_cache.ttl_seconds."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[auto_invoke_cache]\nenabled = true\nttl_seconds = 300\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.auto_invoke_cache_ttl_seconds == 300

    def test_load_config_auto_invoke_cache_max_entry_size_bytes(self, tmp_path: Path):
        """Config should read auto_invoke_cache.max_entry_size_bytes."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[auto_invoke_cache]\nenabled = true\nmax_entry_size_bytes = 2097152\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.auto_invoke_cache_max_entry_size_bytes == 2097152


class TestFeatureFlagsConfig:
    """Test governance and telemetry feature flags."""

    def test_load_config_multi_stack_detection_enabled(self, tmp_path: Path):
        """Config should read multi_stack_detection.enabled."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[multi_stack_detection]\nenabled = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.multi_stack_detection_enabled is True

    def test_load_config_cross_session_state_enabled(self, tmp_path: Path):
        """Config should read cross_session_state.enabled."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[cross_session_state]\nenabled = true\nmax_state_size_bytes = 1048576\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.cross_session_state_enabled is True
        assert cfg.cross_session_state_max_state_size_bytes == 1048576

    def test_load_config_governance_dashboard_enabled(self, tmp_path: Path):
        """Config should read governance_dashboard.enabled."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[governance_dashboard]\nenabled = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.governance_dashboard_enabled is True

    def test_load_config_telemetry_integration_auto_invoke(self, tmp_path: Path):
        """Config should read telemetry.integration.auto_invoke."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[telemetry]\nintegration_auto_invoke = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.telemetry_integration_auto_invoke is True

    def test_load_config_governance_triggers_enabled(self, tmp_path: Path):
        """Config should read governance.triggers.enabled."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[governance]\ntriggers_enabled = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.governance_triggers_enabled is True

    def test_load_config_usage_tracking_enabled(self, tmp_path: Path):
        """Config should read usage_tracking.enabled."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            "[usage_tracking]\nenabled = true\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.usage_tracking_enabled is True


class TestOrchestratorFeaturesConfig:
    """Test OrchestratorFeaturesConfig dataclass."""

    def test_orchestrator_features_config_defaults(self):
        """OrchestratorFeaturesConfig should have correct default values."""
        config = OrchestratorFeaturesConfig()

        assert config.engram is False
        assert config.sdd is False
        assert config.skills is False
        assert config.agents is False

    def test_orchestrator_features_config_with_values(self):
        """OrchestratorFeaturesConfig should accept custom values."""
        config = OrchestratorFeaturesConfig(
            engram=True,
            sdd=True,
            skills=False,
            agents=True,
        )

        assert config.engram is True
        assert config.sdd is True
        assert config.skills is False
        assert config.agents is True


class TestOrchestratorTomlLoading:
    """Test [orchestrator] section TOML loading."""

    def test_load_config_orchestrator_mode_auto_by_default(self, tmp_path: Path):
        """Config should default to orchestrator_mode='auto' when section absent."""
        config_path = tmp_path / "config.toml"
        config_path.write_text("", encoding="utf-8")

        cfg = load_config(str(config_path))

        assert cfg.orchestrator_mode == "auto"

    def test_load_config_orchestrator_mode_gentle_ai(self, tmp_path: Path):
        """Config should read orchestrator mode = gentle-ai."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[orchestrator]\nmode = "gentle-ai"\n',
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.orchestrator_mode == "gentle-ai"

    def test_load_config_orchestrator_mode_none(self, tmp_path: Path):
        """Config should read orchestrator mode = none."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[orchestrator]\nmode = "none"\n',
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.orchestrator_mode == "none"

    def test_load_config_orchestrator_unknown_mode_defaults_to_auto(self, tmp_path: Path):
        """Unknown orchestrator mode should default to 'auto'."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[orchestrator]\nmode = "unknown_value"\n',
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.orchestrator_mode == "auto"

    def test_load_config_orchestrator_features_section(self, tmp_path: Path):
        """Config should read [orchestrator.features] section."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[orchestrator]\nmode = "gentle-ai"\n\n[orchestrator.features]\n'
            "engram = true\nsdd = true\nskills = false\nagents = false\n",
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        assert cfg.orchestrator_mode == "gentle-ai"
        assert cfg.orchestrator_features.engram is True
        assert cfg.orchestrator_features.sdd is True
        assert cfg.orchestrator_features.skills is False
        assert cfg.orchestrator_features.agents is False

    def test_load_config_orchestrator_features_default_when_absent(self, tmp_path: Path):
        """Features should default to OrchestratorFeaturesConfig when section absent."""
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            '[orchestrator]\nmode = "gentle-ai"\n',
            encoding="utf-8",
        )

        cfg = load_config(str(config_path))

        # Features should be the default (all False)
        assert cfg.orchestrator_features.engram is False
        assert cfg.orchestrator_features.sdd is False
        assert cfg.orchestrator_features.skills is False
        assert cfg.orchestrator_features.agents is False
