from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class MetricsSnapshot:
    total_requests_sent: int
    total_responses_received: int
    status_classes: dict[str, int]
    status_codes: dict[int, int]
    response_types: dict[str, int]
    failed_requests: int
    timed_out_requests: int
    avg_response_ms: float
    min_response_ms: float
    max_response_ms: float
    p50_response_ms: float
    p95_response_ms: float
    p99_response_ms: float


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._total_requests_sent = 0
        self._total_responses_received = 0
        self._status_classes: Counter[str] = Counter()
        self._status_codes: Counter[int] = Counter()
        self._response_types: Counter[str] = Counter()
        self._failed_requests = 0
        self._timed_out_requests = 0
        self._response_times_ms: list[float] = []

    async def record_request_sent(self) -> None:
        async with self._lock:
            self._total_requests_sent += 1

    async def record_response(
        self, status_code: int, elapsed_s: float, content_type: str | None, is_failure: bool = False
    ) -> None:
        response_ms = elapsed_s * 1000
        status_class = f"{status_code // 100}xx"
        normalized_type = _normalize_content_type(content_type)
        async with self._lock:
            self._total_responses_received += 1
            self._status_classes[status_class] += 1
            self._status_codes[status_code] += 1
            self._response_types[normalized_type] += 1
            if is_failure:
                self._failed_requests += 1
            self._response_times_ms.append(response_ms)

    async def record_failure(self) -> None:
        async with self._lock:
            self._failed_requests += 1

    async def record_timeout(self) -> None:
        async with self._lock:
            self._timed_out_requests += 1

    async def snapshot(self) -> MetricsSnapshot:
        async with self._lock:
            response_times = list(self._response_times_ms)
            return MetricsSnapshot(
                total_requests_sent=self._total_requests_sent,
                total_responses_received=self._total_responses_received,
                status_classes=dict(self._status_classes),
                status_codes=dict(self._status_codes),
                response_types=dict(self._response_types),
                failed_requests=self._failed_requests,
                timed_out_requests=self._timed_out_requests,
                avg_response_ms=mean(response_times) if response_times else 0.0,
                min_response_ms=min(response_times) if response_times else 0.0,
                max_response_ms=max(response_times) if response_times else 0.0,
                p50_response_ms=_percentile(response_times, 50),
                p95_response_ms=_percentile(response_times, 95),
                p99_response_ms=_percentile(response_times, 99),
            )


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    idx = (len(sorted_values) - 1) * (percentile / 100)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    weight = idx - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return "unknown"
    return content_type.split(";", 1)[0].strip().lower() or "unknown"
