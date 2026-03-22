from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from simulator.metrics import MetricsSnapshot


def render_realtime_summary(snapshot: MetricsSnapshot, elapsed_s: float, active_users: int, total_users: int) -> str:
    return (
        f"[{elapsed_s:7.1f}s] users={active_users}/{total_users} sent={snapshot.total_requests_sent} "
        f"recv={snapshot.total_responses_received} "
        f"fail={snapshot.failed_requests} timeout={snapshot.timed_out_requests} "
        f"avg={snapshot.avg_response_ms:.1f}ms p95={snapshot.p95_response_ms:.1f}ms"
    )


def render_realtime_progress(
    snapshot: MetricsSnapshot,
    elapsed_s: float,
    duration_s: float,
    active_users: int,
    total_users: int,
    width: int = 24,
) -> str:
    safe_duration_s = max(duration_s, 0.001)
    progress = max(0.0, min(elapsed_s / safe_duration_s, 1.0))
    filled = int(round(progress * width))
    bar = f"[{'#' * filled}{'-' * (width - filled)}]"
    remaining_s = max(duration_s - elapsed_s, 0.0)

    return (
        f"{bar} remaining={remaining_s:6.1f}s users={active_users}/{total_users} "
        f"sent={snapshot.total_requests_sent} recv={snapshot.total_responses_received} "
        f"fail={snapshot.failed_requests} timeout={snapshot.timed_out_requests} "
        f"avg={snapshot.avg_response_ms:.1f}ms p95={snapshot.p95_response_ms:.1f}ms"
    )


def render_warmup_progress(
    elapsed_s: float,
    warmup_s: float,
    active_users: int,
    total_users: int,
    width: int = 24,
) -> str:
    safe_warmup_s = max(warmup_s, 0.001)
    progress = max(0.0, min(elapsed_s / safe_warmup_s, 1.0))
    filled = int(round(progress * width))
    bar = f"[{'#' * filled}{'-' * (width - filled)}]"
    remaining_s = max(warmup_s - elapsed_s, 0.0)
    return f"{bar} phase=warmup remaining={remaining_s:6.1f}s users={active_users}/{total_users}"


def render_final_report(snapshot: MetricsSnapshot, elapsed_s: float, tested_url: str, emulated_users: int) -> str:
    lines = [
        "=== Load Test Final Report ===",
        f"Duration: {elapsed_s:.2f}s",
        f"Tested URL: {tested_url}",
        f"Emulated users: {emulated_users}",
        f"Total requests sent: {snapshot.total_requests_sent}",
        f"Total responses received: {snapshot.total_responses_received}",
        f"Failed requests: {snapshot.failed_requests}",
        f"Timed-out requests: {snapshot.timed_out_requests}",
        f"Response times (ms): avg={snapshot.avg_response_ms:.2f} min={snapshot.min_response_ms:.2f} max={snapshot.max_response_ms:.2f}",
        f"Percentiles (ms): p50={snapshot.p50_response_ms:.2f} p95={snapshot.p95_response_ms:.2f} p99={snapshot.p99_response_ms:.2f}",
        f"Status classes: {snapshot.status_classes}",
        f"Status codes: {snapshot.status_codes}",
        f"Response types: {snapshot.response_types}",
    ]
    return "\n".join(lines)


def export_json(path: str, snapshot: MetricsSnapshot, elapsed_s: float) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "duration_s": elapsed_s,
        "metrics": asdict(snapshot),
    }
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_csv(path: str, snapshot: MetricsSnapshot, elapsed_s: float) -> None:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(["metric", "value"])
        writer.writerow(["duration_s", f"{elapsed_s:.4f}"])
        writer.writerow(["total_requests_sent", snapshot.total_requests_sent])
        writer.writerow(["total_responses_received", snapshot.total_responses_received])
        writer.writerow(["failed_requests", snapshot.failed_requests])
        writer.writerow(["timed_out_requests", snapshot.timed_out_requests])
        writer.writerow(["avg_response_ms", f"{snapshot.avg_response_ms:.4f}"])
        writer.writerow(["min_response_ms", f"{snapshot.min_response_ms:.4f}"])
        writer.writerow(["max_response_ms", f"{snapshot.max_response_ms:.4f}"])
        writer.writerow(["p50_response_ms", f"{snapshot.p50_response_ms:.4f}"])
        writer.writerow(["p95_response_ms", f"{snapshot.p95_response_ms:.4f}"])
        writer.writerow(["p99_response_ms", f"{snapshot.p99_response_ms:.4f}"])

        for key, value in sorted(snapshot.status_classes.items()):
            writer.writerow([f"status_class.{key}", value])
        for key, value in sorted(snapshot.status_codes.items()):
            writer.writerow([f"status_code.{key}", value])
        for key, value in sorted(snapshot.response_types.items()):
            writer.writerow([f"response_type.{key}", value])
