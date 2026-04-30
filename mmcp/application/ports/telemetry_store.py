from __future__ import annotations

from typing import Protocol

from mmcp.infrastructure.persistence.session_store import UsageEvent


class TelemetryStorePort(Protocol):
    def record_usage(self, event: UsageEvent) -> None: ...
