import asyncio

from simulator.metrics import MetricsCollector


def test_metrics_collector_snapshot() -> None:
    async def _run() -> None:
        metrics = MetricsCollector()
        await metrics.record_request_sent()
        await metrics.record_request_sent()
        await metrics.record_response(200, elapsed_s=0.1, content_type="application/json; charset=utf-8")
        await metrics.record_response(503, elapsed_s=0.3, content_type="text/plain")
        await metrics.record_timeout()
        await metrics.record_failure()

        snapshot = await metrics.snapshot()
        assert snapshot.total_requests_sent == 2
        assert snapshot.total_responses_received == 2
        assert snapshot.status_classes == {"2xx": 1, "5xx": 1}
        assert snapshot.status_codes == {200: 1, 503: 1}
        assert snapshot.response_types == {"application/json": 1, "text/plain": 1}
        assert snapshot.failed_requests == 1
        assert snapshot.timed_out_requests == 1
        assert snapshot.min_response_ms == 100.0
        assert snapshot.max_response_ms == 300.0

    asyncio.run(_run())
