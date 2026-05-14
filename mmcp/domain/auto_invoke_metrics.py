"""
Auto-Invoke Metrics — async Counter, Histogram, Gauge backed by queue.Queue.

Design:
- Counter, Histogram, Gauge are pure in-memory types keyed by (host, agent, provider, model)
- AutoInvokeMetrics facade composes them and adds async emission via queue.Queue
- Emission is non-blocking: methods record locally then enqueue for background write
- get_summary() returns a structured dict with per-host/per-agent/per-provider/per-model breakdown
"""

from __future__ import annotations

import queue
import threading
from typing import Any, Optional

from mmcp.domain.models import UsageEvent
from mmcp.infrastructure.environment import config as config_module

# Lazy lookup to allow test fixture patches to take effect
from mmcp.infrastructure.persistence.session_store import SessionStore


class Counter:
    """Thread-safe counter metric keyed by (host, agent, provider, model)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str, str], int] = {}
        self._lock = threading.Lock()

    def increment(
        self, host: str, agent: str, provider: str, model: str, *, delta: int = 1
    ) -> None:
        key = (host, agent, provider, model)
        with self._lock:
            self._data[key] = self._data.get(key, 0) + delta

    def get(self, host: str, agent: str, provider: str, model: str) -> int:
        key = (host, agent, provider, model)
        with self._lock:
            return self._data.get(key, 0)

    def total(self) -> int:
        with self._lock:
            return sum(self._data.values())

    def breakdown(self) -> dict[str, int]:
        with self._lock:
            return {
                f"{h}/{a}/{p}/{m}": v
                for (h, a, p, m), v in self._data.items()
            }


class Histogram:
    """Thread-safe histogram of observations keyed by (host, agent, provider, model)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str, str], list[float]] = {}
        self._lock = threading.Lock()

    def record(
        self, host: str, agent: str, provider: str, model: str, value: float
    ) -> None:
        key = (host, agent, provider, model)
        with self._lock:
            if key not in self._data:
                self._data[key] = []
            self._data[key].append(value)

    def get(self, host: str, agent: str, provider: str, model: str) -> list[float]:
        key = (host, agent, provider, model)
        with self._lock:
            return list(self._data.get(key, []))


class Gauge:
    """Thread-safe gauge metric keyed by (host, agent, provider, model)."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str, str, str], float] = {}
        self._lock = threading.Lock()

    def set(
        self, host: str, agent: str, provider: str, model: str, value: float
    ) -> None:
        key = (host, agent, provider, model)
        with self._lock:
            self._data[key] = value

    def get(self, host, agent: str, provider: str, model: str) -> float:
        key = (host, agent, provider, model)
        with self._lock:
            return self._data.get(key, 0.0)


class AutoInvokeMetrics:
    """
    Auto-invoke metrics facade with async emission.

    Composes Counter (invokes), Counter (tokens saved), Histogram (latency),
    and Gauge (current cache size) behind a queue.Queue for non-blocking writes
    to the SessionStore SQLite ledger.
    """

    def __init__(self) -> None:
        self._invokes = Counter()
        self._tokens_saved = Counter()
        self._latencies = Histogram()
        self._cache_size = Gauge()
        self._queue: queue.Queue = queue.Queue()
        self._emitter: Optional[threading.Thread] = None
        self._running = False
        # Start background thread only if tracking is enabled
        if self._enabled:
            self._running = True
            self._emitter = threading.Thread(target=self._emit_loop, daemon=True)
            self._emitter.start()

    @property
    def _enabled(self) -> bool:
        """Lazily read enabled state from config to allow test fixture patches."""
        return config_module.get_config().usage_tracking_enabled

    def _emit_loop(self) -> None:
        """Background thread: drain queue and write to SessionStore."""
        store = SessionStore()
        while self._running:
            try:
                event = self._queue.get(timeout=0.5)
                if event is None:
                    continue
                if isinstance(event, UsageEvent):
                    store.record_usage(event)
            except queue.Empty:
                continue
            except Exception:
                pass  # Non-critical

    def increment_invokes(
        self, host: str, agent: str, provider: str, model: str
    ) -> None:
        """Increment the auto-invoke counter."""
        if not self._enabled:
            return
        self._invokes.increment(host, agent, provider, model)
        self._queue.put(
            UsageEvent(
                session_id="auto-invoke-metrics",
                input_tokens=0,
                output_tokens=0,
                cached_input_tokens=0,
                uncached_input_tokens=0,
                effective_saved_tokens=0,
                host_name=host,
                agent_name=agent,
                provider_name=provider,
                model_name=model,
                tool_name="auto_invoke",
                latency_ms=0.0,
                timestamp=0.0,
            )
        )

    def record_tokens_saved(self, tokens: int) -> None:
        """Record tokens saved via cache."""
        if not self._enabled:
            return
        self._tokens_saved.increment("__total__", "__total__", "__total__", "__total__", delta=tokens)

    def record_latency(self, latency_ms: float) -> None:
        """Record an auto-invoke latency observation."""
        if not self._enabled:
            return
        self._latencies.record("__total__", "__total__", "__total__", "__total__", latency_ms)

    def set_cache_size(self, size: int) -> None:
        """Set current cache entry count."""
        if not self._enabled:
            return
        self._cache_size.set("__total__", "__total__", "__total__", "__total__", float(size))

    def get_summary(self) -> dict[str, Any]:
        """Return structured summary with per-host/per-agent/per-provider/per-model breakdown."""
        breakdown = self._invokes.breakdown()

        hosts: dict[str, int] = {}
        agents: dict[str, int] = {}
        providers: dict[str, int] = {}
        models: dict[str, int] = {}

        for key_str, count in breakdown.items():
            # key_str is "host/agent/provider/model"
            parts = key_str.split("/")
            if len(parts) == 4:
                host, agent, provider, model = parts
                hosts[host] = hosts.get(host, 0) + count
                agents[agent] = agents.get(agent, 0) + count
                providers[provider] = providers.get(provider, 0) + count
                models[model] = models.get(model, 0) + count

        return {
            "total_invokes": self._invokes.total(),
            "total_tokens_saved": self._tokens_saved.total(),
            "hosts": hosts,
            "agents": agents,
            "providers": providers,
            "models": models,
        }

    def shutdown(self) -> None:
        """Stop the background emitter."""
        self._running = False
        if self._emitter is not None:
            self._queue.put(None)
            self._emitter.join(timeout=2.0)
            self._emitter = None
