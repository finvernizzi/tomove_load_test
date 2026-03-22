from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


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
        self._total_requests_sent = 0
        self._total_responses_received = 0
        self._status_classes: Counter[str] = Counter()
        self._status_codes: Counter[int] = Counter()
        self._response_types: Counter[str] = Counter()
        self._failed_requests = 0
        self._timed_out_requests = 0
        self._response_time_sum_ms = 0.0
        self._response_time_min_ms = 0.0
        self._response_time_max_ms = 0.0
        self._latency_bin_size_ms = 10.0
        self._latency_max_ms = 120_000.0
        self._latency_bins = [0] * (int(self._latency_max_ms / self._latency_bin_size_ms) + 1)

    def record_request_sent(self) -> None:
        self._total_requests_sent += 1

    def record_response(
        self, status_code: int, elapsed_s: float, content_type: str | None, is_failure: bool = False
    ) -> None:
        response_ms = elapsed_s * 1000
        status_class = f"{status_code // 100}xx"
        normalized_type = _normalize_content_type(content_type)
        self._total_responses_received += 1
        self._status_classes[status_class] += 1
        self._status_codes[status_code] += 1
        self._response_types[normalized_type] += 1
        if is_failure:
            self._failed_requests += 1

        self._response_time_sum_ms += response_ms
        if self._total_responses_received == 1:
            self._response_time_min_ms = response_ms
            self._response_time_max_ms = response_ms
        else:
            self._response_time_min_ms = min(self._response_time_min_ms, response_ms)
            self._response_time_max_ms = max(self._response_time_max_ms, response_ms)

        bin_idx = int(response_ms / self._latency_bin_size_ms)
        if bin_idx >= len(self._latency_bins):
            bin_idx = len(self._latency_bins) - 1
        self._latency_bins[bin_idx] += 1

    def record_failure(self) -> None:
        self._failed_requests += 1

    def record_timeout(self) -> None:
        self._timed_out_requests += 1

    def snapshot(self) -> MetricsSnapshot:
        total = self._total_responses_received
        return MetricsSnapshot(
            total_requests_sent=self._total_requests_sent,
            total_responses_received=total,
            status_classes=dict(self._status_classes),
            status_codes=dict(self._status_codes),
            response_types=dict(self._response_types),
            failed_requests=self._failed_requests,
            timed_out_requests=self._timed_out_requests,
            avg_response_ms=(self._response_time_sum_ms / total) if total else 0.0,
            min_response_ms=self._response_time_min_ms if total else 0.0,
            max_response_ms=self._response_time_max_ms if total else 0.0,
            p50_response_ms=_percentile_from_histogram(self._latency_bins, total, 50, self._latency_bin_size_ms),
            p95_response_ms=_percentile_from_histogram(self._latency_bins, total, 95, self._latency_bin_size_ms),
            p99_response_ms=_percentile_from_histogram(self._latency_bins, total, 99, self._latency_bin_size_ms),
        )


def _percentile_from_histogram(bins: list[int], total: int, percentile: int, bin_size_ms: float) -> float:
    if total <= 0:
        return 0.0
    target = total * (percentile / 100)
    seen = 0
    for idx, count in enumerate(bins):
        seen += count
        if seen >= target:
            return idx * bin_size_ms
    return (len(bins) - 1) * bin_size_ms


def _normalize_content_type(content_type: str | None) -> str:
    if not content_type:
        return "unknown"
    return content_type.split(";", 1)[0].strip().lower() or "unknown"
