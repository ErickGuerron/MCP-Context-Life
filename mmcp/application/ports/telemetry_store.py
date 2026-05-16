from __future__ import annotations

from typing import Protocol

from mmcp.domain.models import UsageEvent


class TelemetryStorePort(Protocol):
    def record_usage(self, event: UsageEvent) -> None: ...
