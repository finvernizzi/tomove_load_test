from simulator.metrics import MetricsSnapshot
from simulator.reporting import render_final_report, render_realtime_progress, render_realtime_summary, render_warmup_progress


def test_render_realtime_summary_includes_users() -> None:
    snapshot = MetricsSnapshot(
        total_requests_sent=10,
        total_responses_received=8,
        status_classes={"2xx": 8},
        status_codes={200: 8},
        response_types={"application/json": 8},
        failed_requests=1,
        timed_out_requests=1,
        avg_response_ms=100.0,
        min_response_ms=80.0,
        max_response_ms=120.0,
        p50_response_ms=95.0,
        p95_response_ms=115.0,
        p99_response_ms=119.0,
    )

    summary = render_realtime_summary(snapshot, elapsed_s=3.4, active_users=2, total_users=5)
    assert "users=2/5" in summary


def test_render_realtime_progress_includes_remaining_time() -> None:
    snapshot = MetricsSnapshot(
        total_requests_sent=10,
        total_responses_received=8,
        status_classes={"2xx": 8},
        status_codes={200: 8},
        response_types={"application/json": 8},
        failed_requests=1,
        timed_out_requests=1,
        avg_response_ms=100.0,
        min_response_ms=80.0,
        max_response_ms=120.0,
        p50_response_ms=95.0,
        p95_response_ms=115.0,
        p99_response_ms=119.0,
    )

    line = render_realtime_progress(
        snapshot=snapshot,
        elapsed_s=30.0,
        duration_s=120.0,
        active_users=3,
        total_users=20,
    )
    assert "remaining=  90.0s" in line
    assert "users=3/20" in line


def test_render_final_report_includes_url_and_users() -> None:
    snapshot = MetricsSnapshot(
        total_requests_sent=10,
        total_responses_received=8,
        status_classes={"2xx": 8},
        status_codes={200: 8},
        response_types={"application/json": 8},
        failed_requests=1,
        timed_out_requests=1,
        avg_response_ms=100.0,
        min_response_ms=80.0,
        max_response_ms=120.0,
        p50_response_ms=95.0,
        p95_response_ms=115.0,
        p99_response_ms=119.0,
    )

    report = render_final_report(
        snapshot=snapshot,
        elapsed_s=42.5,
        tested_url="https://example.com/v2/messages?domain=mydomain",
        emulated_users=20,
    )

    assert "Tested URL: https://example.com/v2/messages?domain=mydomain" in report
    assert "Emulated users: 20" in report


def test_render_warmup_progress_includes_phase_and_remaining() -> None:
    line = render_warmup_progress(elapsed_s=10.0, warmup_s=40.0, active_users=12, total_users=100)
    assert "phase=warmup" in line
    assert "remaining=  30.0s" in line
    assert "users=12/100" in line
