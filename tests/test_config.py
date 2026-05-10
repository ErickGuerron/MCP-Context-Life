"""
Tests for OrchestratorFeaturesConfig and [orchestrator] TOML loading.
"""

from pathlib import Path

from mmcp.infrastructure.environment.config import (
    OrchestratorFeaturesConfig,
    load_config,
)


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
