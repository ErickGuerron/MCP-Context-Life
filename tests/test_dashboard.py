"""Tests for Phase 7 — Governance helpers integrated into existing telemetry view."""
import pytest
import time
from unittest.mock import patch, MagicMock


class TestGovernanceHelpers:
    """Test governance helpers that integrate into telemetry (NOT as standalone dashboard)."""

    def test_get_governance_info_returns_dict_when_tracking_enabled(self):
        """get_governance_info() returns a dict with governance metrics when tracking is on."""
        import sys
        from unittest.mock import MagicMock

        # Block SessionStore at module level BEFORE importing anything
        with patch.dict(sys.modules, {"mmcp.infrastructure.persistence.session_store": MagicMock()}):
            # Now import after SessionStore is blocked
            from mmcp.presentation.cli.dashboard import get_governance_info

            mock_summary = {
                "total_invokes": 42,
                "total_tokens_saved": 15000,
                "hosts": {"localhost": 42},
                "agents": {"orchestrator": 42},
            }

            with patch("mmcp.infrastructure.environment.config.get_config") as mock_cfg:
                mock_cfg.return_value.usage_tracking_enabled = True
                with patch("mmcp.domain.auto_invoke_metrics.AutoInvokeMetrics") as mock_cls:
                    mock_instance = MagicMock()
                    mock_instance.get_summary.return_value = mock_summary
                    mock_instance._latencies.get.return_value = [10.0, 20.0, 30.0]
                    mock_instance._last_updated = time.time()  # not stale
                    mock_cls.return_value = mock_instance

                    info = get_governance_info()

        assert info is not None
        assert info["cache_status"] == "warm"  # 42 invocations > 0
        assert info["governance_priority"] == "medium"  # 42 > 20 and <= 100
        assert info["total_invokes"] == 42
        assert info["tokens_saved"] == 15000

    def test_get_governance_info_returns_none_when_tracking_disabled(self):
        """get_governance_info() returns None when usage_tracking is disabled."""
        from mmcp.presentation.cli.dashboard import get_governance_info

        with patch("mmcp.infrastructure.environment.config.get_config") as mock_cfg:
            mock_cfg.return_value.usage_tracking_enabled = False

            info = get_governance_info()

        assert info is None

    def test_get_governance_info_returns_none_on_exception(self):
        """get_governance_info() returns None gracefully when metrics unavailable."""
        from mmcp.presentation.cli.dashboard import get_governance_info

        with patch("mmcp.infrastructure.environment.config.get_config") as mock_cfg:
            mock_cfg.return_value.usage_tracking_enabled = True
            with patch("mmcp.domain.auto_invoke_metrics.AutoInvokeMetrics", side_effect=RuntimeError("DB not ready")):
                info = get_governance_info()

        assert info is None

    def test_cache_cold_when_no_invokes(self):
        """Cache status is 'cold' when total_invokes == 0."""
        import sys
        from unittest.mock import MagicMock

        with patch.dict(sys.modules, {"mmcp.infrastructure.persistence.session_store": MagicMock()}):
            from mmcp.presentation.cli.dashboard import get_governance_info

            mock_summary = {
                "total_invokes": 0,
                "total_tokens_saved": 0,
                "hosts": {},
                "agents": {},
            }

            with patch("mmcp.infrastructure.environment.config.get_config") as mock_cfg:
                mock_cfg.return_value.usage_tracking_enabled = True
                with patch("mmcp.domain.auto_invoke_metrics.AutoInvokeMetrics") as mock_cls:
                    mock_instance = MagicMock()
                    mock_instance.get_summary.return_value = mock_summary
                    mock_instance._latencies.get.return_value = []
                    mock_instance._last_updated = time.time()
                    mock_cls.return_value = mock_instance

                    info = get_governance_info()

        assert info is not None
        assert info["cache_status"] == "cold"
        assert info["governance_priority"] == "low"  # 0 <= 20

    def test_priority_high_when_many_invokes(self):
        """Priority is 'high' when invocations > 100."""
        import sys
        from unittest.mock import MagicMock

        with patch.dict(sys.modules, {"mmcp.infrastructure.persistence.session_store": MagicMock()}):
            from mmcp.presentation.cli.dashboard import get_governance_info

            mock_summary = {
                "total_invokes": 150,
                "total_tokens_saved": 50000,
                "hosts": {"host1": 150},
                "agents": {"agent1": 150},
            }

            with patch("mmcp.infrastructure.environment.config.get_config") as mock_cfg:
                mock_cfg.return_value.usage_tracking_enabled = True
                with patch("mmcp.domain.auto_invoke_metrics.AutoInvokeMetrics") as mock_cls:
                    mock_instance = MagicMock()
                    mock_instance.get_summary.return_value = mock_summary
                    mock_instance._latencies.get.return_value = []
                    mock_instance._last_updated = time.time()
                    mock_cls.return_value = mock_instance

                    info = get_governance_info()

        assert info is not None
        assert info["governance_priority"] == "high"


class TestGovernanceFormatting:
    """Test format_governance_lines() for tasteful integration into telemetry."""

    def test_format_governance_lines_one_line_warm_low(self):
        """Format returns one line: Cache + Priority, no staleness."""
        from mmcp.presentation.cli.dashboard import format_governance_lines

        info = {
            "cache_status": "warm",
            "governance_priority": "low",
            "is_stale": False,
        }
        lines = format_governance_lines(info)

        assert len(lines) == 1
        assert "warm" in lines[0].lower()
        assert "low" in lines[0].lower()

    def test_format_governance_lines_two_lines_stale(self):
        """Format returns two lines when stale: Cache+Priority + staleness warning."""
        from mmcp.presentation.cli.dashboard import format_governance_lines

        info = {
            "cache_status": "warm",
            "governance_priority": "high",
            "is_stale": True,
        }
        lines = format_governance_lines(info)

        assert len(lines) == 2
        assert "warm" in lines[0].lower()
        assert "high" in lines[0].lower()
        assert "stale" in lines[1].lower()

    def test_format_minimal_no_saturation(self):
        """Output is intentionally minimal — max 2 lines to avoid saturating telemetry view."""
        from mmcp.presentation.cli.dashboard import format_governance_lines

        # Normal case — no staleness
        info = {"cache_status": "cold", "governance_priority": "medium", "is_stale": False}
        lines = format_governance_lines(info)
        assert len(lines) <= 2  # Hard requirement: never more than 2 lines

        # Stale case
        info_stale = {"cache_status": "cold", "governance_priority": "medium", "is_stale": True}
        lines_stale = format_governance_lines(info_stale)
        assert len(lines_stale) <= 2  # Still max 2 lines