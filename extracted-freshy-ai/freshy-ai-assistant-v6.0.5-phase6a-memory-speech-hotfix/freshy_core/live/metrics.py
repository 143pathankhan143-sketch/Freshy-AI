from __future__ import annotations

import threading
import time
from typing import Any, Dict

from .schemas import LiveMetrics


class LatencyTracker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._metrics = LiveMetrics()

    def reset_turn(self) -> None:
        with self._lock:
            reconnects = self._metrics.reconnect_count
            tools = self._metrics.tool_call_count
            underruns = self._metrics.output_buffer_underruns
            self._metrics = LiveMetrics(
                reconnect_count=reconnects,
                tool_call_count=tools,
                output_buffer_underruns=underruns,
            )

    def mark(self, field: str, *, once: bool = True) -> None:
        with self._lock:
            if not hasattr(self._metrics, field):
                return
            if once and getattr(self._metrics, field) is not None:
                return
            setattr(self._metrics, field, time.monotonic())

    def increment(self, field: str, amount: int = 1) -> None:
        with self._lock:
            if not hasattr(self._metrics, field):
                return
            setattr(self._metrics, field, int(getattr(self._metrics, field) or 0) + amount)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            data = self._metrics.model_dump()
            data["durations"] = self._metrics.durations()
            return data
