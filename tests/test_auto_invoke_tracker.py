"""Tests for auto_invoke_tracker - Phase 8 telemetry integration."""

import queue
import tempfile
import threading
import time
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

from mmcp.domain.models import UsageEvent


class TestUsageEventFields:
    """Test that UsageEvent supports auto_invoke event_type and derived accounting_mode."""

    def test_usage_event_has_event_type_field(self):
        """RED: UsageEvent must have event_type field for auto_invoke tracking."""
        event = UsageEvent(
            session_id="test-session",
            event_type="auto_invoke",
        )
        assert event.event_type == "auto_invoke"

    def test_usage_event_has_accounting_mode_field(self):
        """RED: UsageEvent must have accounting_mode field for derived/captured modes."""
        event = UsageEvent(
            session_id="test-session",
            accounting_mode="derived",
        )
        assert event.accounting_mode == "derived"

    def test_usage_event_auto_invoke_complete_construction(self):
        """RED: Full UsageEvent construction with auto_invoke event_type and derived accounting_mode."""
        now = time.time()
        event = UsageEvent(
            session_id="sess-123",
            event_type="auto_invoke",
            accounting_mode="derived",
            input_tokens=100,
            output_tokens=50,
            cached_input_tokens=30,
            uncached_input_tokens=70,
            effective_saved_tokens=30,
            host_name="context-life-server",
            agent_name="gentle-ai",
            provider_name="openai",
            model_name="gpt-4",
            tool_name="auto_invoke",
            latency_ms=12.5,
            timestamp=now,
        )
        assert event.session_id == "sess-123"
        assert event.event_type == "auto_invoke"
        assert event.accounting_mode == "derived"
        assert event.input_tokens == 100
        assert event.latency_ms == 12.5


class TestAutoInvokeTrackerConstruction:
    """Test AutoInvokeTracker constructs UsageEvent and emits via background queue."""

    def test_tracker_creates_usage_event_with_auto_invoke_type(self, monkeypatch):
        """RED: AutoInvokeTracker.log() creates UsageEvent with event_type='auto_invoke'."""
        from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

        # Ensure telemetry_integration_auto_invoke is True so bypass doesn't trigger
        monkeypatch.setattr(
            "mmcp.infrastructure.telemetry.auto_invoke_tracker.get_config",
            lambda: MagicMock(telemetry_integration_auto_invoke=True),
        )

        captured = {}

        def mock_log(event):
            captured["event"] = event

        q = queue.Queue()
        tracker = AutoInvokeTracker(log_func=mock_log, event_queue=q)
        tracker.start()

        tracker.log(
            session_id="sess-abc",
            latency_ms=5.0,
            input_tokens=200,
            output_tokens=100,
            cached_input_tokens=50,
            uncached_input_tokens=150,
            effective_saved_tokens=50,
            host_name="test-host",
            agent_name="test-agent",
            provider_name="openai",
            model_name="gpt-4",
        )
        tracker.flush()

        event = captured["event"]
        assert isinstance(event, UsageEvent)
        assert event.event_type == "auto_invoke"
        assert event.accounting_mode == "derived"
        assert event.session_id == "sess-abc"
        assert event.latency_ms == 5.0

        tracker.stop()

    def test_tracker_uses_background_thread_queue(self, monkeypatch):
        """RED: AutoInvokeTracker emits telemetry via background thread queue."""
        from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

        # Ensure telemetry_integration_auto_invoke is True so bypass doesn't trigger
        monkeypatch.setattr(
            "mmcp.infrastructure.telemetry.auto_invoke_tracker.get_config",
            lambda: MagicMock(telemetry_integration_auto_invoke=True),
        )

        events_received = []
        stop_event = threading.Event()

        def background_consumer(q, events, stop):
            while not stop.is_set():
                try:
                    item = q.get(timeout=0.1)
                    if item is None:
                        break
                    events.append(item)
                except queue.Empty:
                    pass

        q = queue.Queue()
        tracker = AutoInvokeTracker(event_queue=q)
        tracker.start()

        consumer_thread = Thread(target=background_consumer, args=(q, events_received, stop_event))
        consumer_thread.start()

        tracker.log(
            session_id="sess-thread",
            latency_ms=3.0,
            input_tokens=100,
            output_tokens=50,
            cached_input_tokens=25,
            uncached_input_tokens=75,
            effective_saved_tokens=25,
            host_name="thread-host",
            agent_name="thread-agent",
            provider_name="anthropic",
            model_name="claude-3",
        )

        tracker.flush()
        stop_event.set()
        consumer_thread.join()

        assert len(events_received) == 1
        event = events_received[0]
        assert event.event_type == "auto_invoke"

        tracker.stop()


class TestQueueRetryLogic:
    """Test queue retry logic when TelemetryService unavailable."""

    def test_retry_on_telemetry_service_failure(self, monkeypatch):
        """RED: Queue retries with warning log when TelemetryService unavailable."""
        from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

        # Ensure telemetry_integration_auto_invoke is True so bypass doesn't trigger
        monkeypatch.setattr(
            "mmcp.infrastructure.telemetry.auto_invoke_tracker.get_config",
            lambda: MagicMock(telemetry_integration_auto_invoke=True),
        )

        call_count = 0

        def flaky_log(event):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("TelemetryService unavailable")

        q = queue.Queue()
        tracker = AutoInvokeTracker(log_func=flaky_log, event_queue=q, max_retries=3, retry_delay=0.01)
        tracker.start()

        tracker.log(
            session_id="sess-retry",
            latency_ms=1.0,
            input_tokens=10,
            output_tokens=5,
            cached_input_tokens=2,
            uncached_input_tokens=8,
            effective_saved_tokens=2,
            host_name="retry-host",
            agent_name="retry-agent",
            provider_name="openai",
            model_name="gpt-3.5",
        )

        # Give time for retry processing
        tracker.flush()

        # Should have retried and eventually logged warning, not error
        # (Implementation detail: we track calls to verify retry happened)
        assert call_count >= 2, f"Expected at least 2 calls (initial + retry), got {call_count}"

        tracker.stop()


class TestOverheadVerification:
    """Test overhead verification - must be < 5ms per invocation."""

    def test_overhead_under_5ms(self):
        """RED: AutoInvokeTracker.log() adds < 5ms overhead per invocation."""
        from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

        noop_log = lambda event: None
        tracker = AutoInvokeTracker(log_func=noop_log)

        # Warm up
        tracker.log(
            session_id="warmup",
            latency_ms=0,
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=0,
            uncached_input_tokens=0,
            effective_saved_tokens=0,
            host_name="w",
            agent_name="w",
            provider_name="w",
            model_name="w",
        )

        # Measure
        iterations = 100
        start = time.perf_counter()
        for _ in range(iterations):
            tracker.log(
                session_id="measure",
                latency_ms=0,
                input_tokens=0,
                output_tokens=0,
                cached_input_tokens=0,
                uncached_input_tokens=0,
                effective_saved_tokens=0,
                host_name="m",
                agent_name="m",
                provider_name="m",
                model_name="m",
            )
        end = time.perf_counter()

        avg_ms = ((end - start) / iterations) * 1000
        assert avg_ms < 5.0, f"Overhead {avg_ms:.2f}ms exceeds 5ms limit"


class TestConfigBypass:
    """Test telemetry.integration.auto_invoke: false bypass."""

    def test_bypass_when_flag_disabled(self):
        """RED: AutoInvokeTracker skips emission when telemetry.integration.auto_invoke is False."""
        from mmcp.infrastructure.environment.config import get_config, reset_config

        # Save original
        original_value = None

        reset_config()
        cfg = get_config()
        original_value = cfg.telemetry_integration_auto_invoke

        # Set to False
        cfg.telemetry_integration_auto_invoke = False

        try:
            from mmcp.infrastructure.telemetry.auto_invoke_tracker import AutoInvokeTracker

            call_count = 0

            def counting_log(event):
                nonlocal call_count
                call_count += 1

            tracker = AutoInvokeTracker(log_func=counting_log)
            tracker.log(
                session_id="sess-bypass",
                latency_ms=1.0,
                input_tokens=10,
                output_tokens=5,
                cached_input_tokens=2,
                uncached_input_tokens=8,
                effective_saved_tokens=2,
                host_name="bypass-host",
                agent_name="bypass-agent",
                provider_name="openai",
                model_name="gpt-3.5",
            )

            # With flag False, log should not be called
            assert call_count == 0, f"Expected 0 calls but got {call_count} - bypass not working"
        finally:
            cfg.telemetry_integration_auto_invoke = original_value
            reset_config()