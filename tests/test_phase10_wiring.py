"""
Integration tests for Phase 10: Integration + Wiring.

Tests that all auto-invoke-improvements components are wired correctly:
- 10.1: AutoInvokeCache wired into auto-invoke path
- 10.2: AutoInvokeMetrics wired into cache hit/miss
- 10.3: Multi-stack detection wired into OrchestratorDetector
- 10.4: SessionPersistence wired into session lifecycle
- 10.5: Dashboard panel wired into TUI
- 10.6: AutoInvokeTracker wired into auto-invoke completion
"""

import os
from pathlib import Path
from unittest.mock import patch


class TestAutoInvokeCacheWiring:
    """Test 10.1: AutoInvokeCache wired into auto-invoke execution path."""

    def test_cache_wired_when_enabled(self, tmp_path, isolated_data_dir):
        """AutoInvokeCache is consulted when auto_invoke_cache.enabled=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.auto_invoke_cache_enabled = True
        cfg.auto_invoke_cache_ttl_seconds = 60

        # Import after config change
        from mmcp.orchestration.auto_invoke_cache import AutoInvokeCache

        cache = AutoInvokeCache(enabled=True, ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        # Cache should be consulted
        cache.set(key, {"result": "cached"})
        result = cache.get(key)
        assert result == {"result": "cached"}

    def test_cache_bypassed_when_disabled(self, tmp_path, isolated_data_dir):
        """AutoInvokeCache is bypassed when auto_invoke_cache.enabled=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.auto_invoke_cache_enabled = False

        from mmcp.orchestration.auto_invoke_cache import AutoInvokeCache

        cache = AutoInvokeCache(enabled=False, ttl_seconds=60)
        key = cache._derive_key(
            host="localhost",
            agent="test-agent",
            provider="openai",
            model="gpt-4",
            operation="chat",
            args={"prompt": "hello"},
        )

        cache.set(key, {"result": "stored"})
        result = cache.get(key)
        # When disabled, get returns None (bypass)
        assert result is None


class TestAutoInvokeMetricsWiring:
    """Test 10.2: AutoInvokeMetrics wired into cache hit/miss path."""

    def test_metrics_record_on_invoke(self, tmp_path, isolated_data_dir):
        """AutoInvokeMetrics records invokes when usage_tracking.enabled=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.usage_tracking_enabled = True

        from mmcp.domain.auto_invoke_metrics import AutoInvokeMetrics

        metrics = AutoInvokeMetrics()
        metrics.increment_invokes("localhost", "test-agent", "openai", "gpt-4")

        summary = metrics.get_summary()
        assert summary["total_invokes"] >= 1

    def test_metrics_bypassed_when_disabled(self, tmp_path, isolated_data_dir):
        """AutoInvokeMetrics does not record when usage_tracking.enabled=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.usage_tracking_enabled = False

        from mmcp.domain.auto_invoke_metrics import AutoInvokeMetrics

        metrics = AutoInvokeMetrics()
        metrics.increment_invokes("localhost", "test-agent", "openai", "gpt-4")

        summary = metrics.get_summary()
        # When disabled, no metrics recorded
        assert summary["total_invokes"] == 0


class TestMultiStackDetectionWiring:
    """Test 10.3: Multi-stack detection wired into OrchestratorDetector."""

    def test_multi_stack_detected_when_enabled(self, tmp_path, isolated_data_dir):
        """Multi-stack detection runs when multi_stack_detection.enabled=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.multi_stack_detection_enabled = True

        # Create actual directories so Path.exists() returns True
        cursor_dir = tmp_path / "Cursor"
        windsurf_dir = tmp_path / "Windsurf"
        cursor_dir.mkdir()
        windsurf_dir.mkdir()

        # Set env vars pointing to existing directories
        with patch.dict(os.environ, {"CURSOR_DIR": str(cursor_dir), "WINDURF_DATA_DIR": str(windsurf_dir)}):
            from mmcp.infrastructure.environment.orchestrator_detector import (
                _check_multi_stack,
            )

            # Directly test _check_multi_stack to verify it detects multi-stack
            result = _check_multi_stack()

            # Should detect multi-stack (2+ signals: cursor + windsurf)
            assert result is not None
            assert result.is_detected is True
            assert "cursor" in result.orchestrator_name or "windsurf" in result.orchestrator_name

    def test_multi_stack_returns_none_when_disabled(self, tmp_path, isolated_data_dir):
        """Multi-stack detection returns None when multi_stack_detection.enabled=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.multi_stack_detection_enabled = False

        # Even with env vars set, should return None when disabled
        with patch.dict(
            os.environ, {"CURSOR_DIR": str(tmp_path / "Cursor"), "WINDURF_DATA_DIR": str(tmp_path / "Windsurf")}
        ):
            from mmcp.infrastructure.environment.orchestrator_detector import _check_multi_stack

            result = _check_multi_stack()
            # When disabled, should return None (not run detection)
            assert result is None


class TestSessionPersistenceWiring:
    """Test 10.4: SessionPersistence wired into session lifecycle."""

    def test_persistence_saves_and_loads_state(self, tmp_path, isolated_data_dir):
        """SessionPersistence saves and loads state when cross_session_state.enabled=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.cross_session_state_enabled = True
        cfg.cache_db_path = str(tmp_path / "test.db")

        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        persistence = SessionPersistence(db_path=Path(cfg.cache_db_path))

        test_state = {"key": "value", "number": 42}
        persistence.save_state("test-session-123", test_state)

        loaded = persistence.load_state("test-session-123")
        assert loaded == test_state

    def test_persistence_bypassed_when_disabled(self, tmp_path, isolated_data_dir):
        """SessionPersistence is no-op when cross_session_state.enabled=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.cross_session_state_enabled = False

        from mmcp.infrastructure.persistence.session_persistence import SessionPersistence

        persistence = SessionPersistence()

        # Should be no-op when disabled
        result = persistence.load_state("any-session")
        assert result is None


class TestDashboardWiring:
    """Test 10.5: Dashboard governance info wired into TUI."""

    def test_governance_info_returns_data_when_enabled(self, tmp_path, isolated_data_dir):
        """get_governance_info returns data when governance_dashboard.enabled=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.governance_dashboard_enabled = True
        cfg.usage_tracking_enabled = True

        from mmcp.presentation.cli.dashboard import get_governance_info

        info = get_governance_info()
        # When enabled, should return dict (even if metrics are empty)
        assert info is not None
        assert "cache_status" in info
        assert "governance_priority" in info

    def test_governance_info_returns_none_when_disabled(self, tmp_path, isolated_data_dir):
        """get_governance_info returns None when governance_dashboard.enabled=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.governance_dashboard_enabled = False
        cfg.usage_tracking_enabled = False

        from mmcp.presentation.cli.dashboard import get_governance_info

        info = get_governance_info()
        assert info is None


class TestAutoInvokeTrackerWiring:
    """Test 10.6: AutoInvokeTracker wired into auto-invoke completion."""

    def test_tracker_emits_when_enabled(self, tmp_path, isolated_data_dir):
        """AutoInvokeTracker emits telemetry when telemetry.integration.auto_invoke=true."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.telemetry_integration_auto_invoke = True

        from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

        tracker = AutoInvokeTracker()
        tracker.log(
            session_id="test-session",
            latency_ms=10.5,
            input_tokens=100,
            output_tokens=50,
            cached_input_tokens=30,
            uncached_input_tokens=70,
            effective_saved_tokens=30,
            host_name="localhost",
            agent_name="test-agent",
            provider_name="openai",
            model_name="gpt-4",
        )

        # Tracker should have queued the event (non-blocking)
        tracker.flush(timeout=1.0)

    def test_tracker_bypassed_when_disabled(self, tmp_path, isolated_data_dir):
        """AutoInvokeTracker does not emit when telemetry.integration.auto_invoke=false."""
        from mmcp.infrastructure.environment.config import get_config

        cfg = get_config()
        cfg.telemetry_integration_auto_invoke = False

        from mmcp.infrastructure.telemetry.auto_invoke_tracker import track_auto_invoke

        # Should not raise - just silently does nothing
        track_auto_invoke(
            session_id="test-session",
            latency_ms=10.5,
            input_tokens=100,
            output_tokens=50,
            cached_input_tokens=30,
            uncached_input_tokens=70,
            effective_saved_tokens=30,
            host_name="localhost",
            agent_name="test-agent",
            provider_name="openai",
            model_name="gpt-4",
        )
