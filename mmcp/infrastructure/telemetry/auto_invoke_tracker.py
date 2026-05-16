"""
Auto Invoke Tracker - Phase 8 Telemetry Integration.

Constructs UsageEvent with event_type="auto_invoke" and accounting_mode="derived",
emits via background thread queue to avoid blocking MCP tool execution.
"""

from __future__ import annotations

import atexit
import logging
import queue
import threading
import time
from typing import Callable, Optional

from mmcp.domain.models import UsageEvent
from mmcp.infrastructure.environment.config import get_config

_logger = logging.getLogger(__name__)


class AutoInvokeTracker:
    """
    Async telemetry tracker for auto-invoke events.

    Constructs UsageEvent with event_type="auto_invoke" and accounting_mode="derived",
    then queues it for background emission via TelemetryService.

    Thread-safe, non-blocking to MCP tool execution.
    """

    def __init__(
        self,
        log_func: Optional[Callable[[UsageEvent], None]] = None,
        event_queue: Optional[queue.Queue] = None,
        max_retries: int = 3,
        retry_delay: float = 0.05,
    ):
        """
        Initialize the auto invoke tracker.

        Args:
            log_func: Optional custom log function. If None, uses TelemetryService.log_usage.
            event_queue: Optional custom queue for testing. If None, creates internal queue.
            max_retries: Max retry attempts when log_func raises exception.
            retry_delay: Seconds to wait between retries.
        """
        self._log_func = log_func
        self._queue = event_queue if event_queue is not None else queue.Queue()
        self._passive_queue_mode = event_queue is not None and log_func is None
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started = False

    def _get_log_func(self) -> Callable[[UsageEvent], None]:
        """Get the log function, defaulting to TelemetryService.log_usage."""
        if self._log_func is not None:
            return self._log_func
        from mmcp.infrastructure.telemetry.telemetry_service import TelemetryService

        store = None
        try:
            from mmcp.infrastructure.persistence.session_store import SessionStore

            config = get_config()
            store = SessionStore(config.resolve_cache_db_path())
        except Exception:
            pass
        if store is not None:
            svc = TelemetryService(store)
            return svc.log_usage
        # Fallback to module-level log_usage
        from mmcp.infrastructure.telemetry.telemetry_service import log_usage

        return log_usage

    def _worker_loop(self) -> None:
        """Background worker that processes the queue and emits telemetry."""
        log_func = self._get_log_func()

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.1)
                if item is None:
                    break
                event = item
                self._emit_with_retry(event, log_func)
            except queue.Empty:
                continue
            except Exception as e:
                _logger.warning(f"AutoInvokeTracker queue processing error: {e}")

    def _emit_with_retry(self, event: UsageEvent, log_func: Callable[[UsageEvent], None]) -> None:
        """Emit event with retry logic on failure, logging warning (not error)."""
        for attempt in range(1, self._max_retries + 1):
            try:
                log_func(event)
                return
            except Exception as e:
                if attempt < self._max_retries:
                    _logger.warning(
                        f"AutoInvokeTracker: TelemetryService unavailable (attempt {attempt}/{self._max_retries}), "
                        f"retrying in {self._retry_delay}s: {e}"
                    )
                    time.sleep(self._retry_delay)
                else:
                    _logger.warning(
                        f"AutoInvokeTracker: Failed to emit telemetry after {self._max_retries} attempts "
                        f"(event_type={event.event_type}, session={event.session_id}): {e}"
                    )

    def start(self) -> None:
        """Start the background worker thread if not already running."""
        if self._started:
            return
        if self._passive_queue_mode:
            self._started = True
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self._started = True
        atexit.register(self.stop)

    def stop(self) -> None:
        """Stop the background worker thread gracefully."""
        if self._passive_queue_mode:
            self._started = False
            return
        self._stop_event.set()
        if self._queue is not None:
            self._queue.put(None)  # Sentinel to unblock worker
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None
        self._started = False

    def log(
        self,
        session_id: str,
        latency_ms: float,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int,
        uncached_input_tokens: int,
        effective_saved_tokens: int,
        host_name: str,
        agent_name: str,
        provider_name: str,
        model_name: str,
    ) -> None:
        """
        Queue an auto-invoke telemetry event for background emission.

        This method is non-blocking - it constructs the UsageEvent and puts it
        on the queue for background processing. MCP tool execution is not affected.

        Args:
            session_id: Session identifier
            latency_ms: Tool invocation latency in milliseconds
            input_tokens: Token count for input
            output_tokens: Token count for output
            cached_input_tokens: Tokens from cache
            uncached_input_tokens: Tokens not from cache
            effective_saved_tokens: Tokens saved via auto-invoke
            host_name: Host running Context-Life
            agent_name: Orchestrator agent name
            provider_name: LLM provider (openai, anthropic, etc.)
            model_name: Model name (gpt-4, claude-3, etc.)
        """
        # Check config bypass flag
        try:
            config = get_config()
            if not config.telemetry_integration_auto_invoke:
                return
        except Exception:
            # If config unavailable, allow emission
            pass

        # Ensure worker is started
        self.start()

        event = UsageEvent(
            session_id=session_id,
            event_type="auto_invoke",
            accounting_mode="derived",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens,
            uncached_input_tokens=uncached_input_tokens,
            effective_saved_tokens=effective_saved_tokens,
            host_name=host_name,
            agent_name=agent_name,
            provider_name=provider_name,
            model_name=model_name,
            tool_name="auto_invoke",
            latency_ms=round(latency_ms, 2),
            timestamp=time.time(),
        )

        try:
            self._queue.put_nowait(event)
        except queue.Full:
            _logger.warning(f"AutoInvokeTracker: Queue full, dropping event for session {session_id}")

    def flush(self, timeout: float = 1.0) -> None:
        """
        Wait for all queued events to be processed by the worker.

        For testing purposes - allows synchronizing on queue completion.
        """
        if not self._started:
            return
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._queue.empty():
                return
            time.sleep(0.05)


# Module-level singleton tracker instance
_tracker: Optional[AutoInvokeTracker] = None


def get_tracker() -> AutoInvokeTracker:
    """Get or create the module-level AutoInvokeTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = AutoInvokeTracker()
    return _tracker


def track_auto_invoke(
    session_id: str,
    latency_ms: float,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int,
    uncached_input_tokens: int,
    effective_saved_tokens: int,
    host_name: str,
    agent_name: str,
    provider_name: str,
    model_name: str,
) -> None:
    """
    Convenience function to track an auto-invoke event.

    Uses the module-level singleton tracker.
    """
    get_tracker().log(
        session_id=session_id,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        uncached_input_tokens=uncached_input_tokens,
        effective_saved_tokens=effective_saved_tokens,
        host_name=host_name,
        agent_name=agent_name,
        provider_name=provider_name,
        model_name=model_name,
    )
