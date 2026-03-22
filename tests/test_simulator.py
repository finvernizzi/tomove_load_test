import asyncio

import httpx

from simulator.config import LoadTestConfig
from simulator.simulator import LoadSimulator


def test_simulator_sends_headers_and_records_responses() -> None:
    seen_header_values: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_header_values.append(request.headers["X-Domain"])
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 1,
                "interval_s": 0.05,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 0.12,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "GET",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                    "timeout_s": 2,
                    "headers": {
                        "X-Domain": "{{DOMAIN}}",
                    },
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        snapshot, _elapsed = asyncio.run(LoadSimulator(config).run())
        assert snapshot.total_requests_sent >= 1
        assert snapshot.total_responses_received >= 1
        assert snapshot.status_codes.get(200, 0) >= 1
        assert all(value == "my-domain" for value in seen_header_values)
    finally:
        httpx.AsyncClient = original_client


def test_simulator_treats_4xx_as_failure_by_default() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, headers={"content-type": "application/json"}, json={"error": "not found"})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 1,
                "interval_s": 0.05,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 0.12,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "GET",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                    "timeout_s": 2,
                    "headers": {},
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        snapshot, _elapsed = asyncio.run(LoadSimulator(config).run())
        assert snapshot.status_codes.get(404, 0) >= 1
        assert snapshot.failed_requests >= 1
    finally:
        httpx.AsyncClient = original_client


def test_simulator_stops_early_when_stop_event_is_set() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    async def _run() -> float:
        httpx.AsyncClient = PatchedAsyncClient
        try:
            config = LoadTestConfig.from_dict(
                {
                    "host": "api.example.com",
                    "domain": "my-domain",
                    "api_version": "v1",
                    "users": 1,
                    "interval_s": 0.05,
                    "random_delay_min_s": 0.0,
                    "random_delay_max_s": 0.0,
                    "duration_s": 5.0,
                    "ramp_up_s": 0,
                    "summary_interval_s": 1,
                    "radius_m": 5000,
                    "request": {
                        "method": "GET",
                        "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                        "timeout_s": 2,
                        "headers": {},
                    },
                    "geo": {
                        "area": "Turin",
                        "named_areas": {
                            "Turin": {
                                "min_lat": 45.0,
                                "max_lat": 45.1,
                                "min_lng": 7.6,
                                "max_lng": 7.7,
                            }
                        },
                    },
                    "export": {},
                }
            )
            stop_event = asyncio.Event()

            async def _trigger_stop() -> None:
                await asyncio.sleep(0.1)
                stop_event.set()

            asyncio.create_task(_trigger_stop())
            _snapshot, elapsed = await LoadSimulator(config).run(stop_event=stop_event)
            return elapsed
        finally:
            httpx.AsyncClient = original_client

    elapsed = asyncio.run(_run())
    assert elapsed < 2.0


def test_simulator_post_body_template_renders_random_coordinates() -> None:
    seen_bodies: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(request.content.decode("utf-8"))
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 1,
                "interval_s": 0.05,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 0.12,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "POST",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages",
                    "body_template": '{"lat":"{{RANDOM_LAT}}","lng":"{{RANDOM_LNG}}","radius":"{{RADIUS}}"}',
                    "timeout_s": 2,
                    "headers": {
                        "Content-Type": "application/json",
                    },
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        snapshot, _elapsed = asyncio.run(LoadSimulator(config).run())
        assert snapshot.total_responses_received >= 1
        assert len(seen_bodies) >= 1
        assert all('"lat":"' in body and '"lng":"' in body for body in seen_bodies)
    finally:
        httpx.AsyncClient = original_client


def test_simulator_respects_duration_without_catchup_overrun() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.7)
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 5,
                "interval_s": 0.1,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 1.0,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "GET",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                    "timeout_s": 2,
                    "headers": {},
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        _snapshot, elapsed = asyncio.run(LoadSimulator(config).run())
        assert elapsed < 2.2
    finally:
        httpx.AsyncClient = original_client


def test_simulator_excludes_warmup_requests_from_stats() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 1,
                "interval_s": 0.5,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 0.05,
                "warmup_s": 0.4,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "GET",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                    "timeout_s": 2,
                    "headers": {},
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        snapshot, elapsed = asyncio.run(LoadSimulator(config).run())
        assert snapshot.total_requests_sent == 0
        assert snapshot.total_responses_received == 0
        assert 0.0 <= elapsed <= 0.25
    finally:
        httpx.AsyncClient = original_client


def test_simulator_enforces_hard_total_request_timeout() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.2)
        return httpx.Response(200, headers={"content-type": "application/json"}, json={"ok": True})

    original_client = httpx.AsyncClient

    class PatchedAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            super().__init__(*args, **kwargs)

    httpx.AsyncClient = PatchedAsyncClient
    try:
        config = LoadTestConfig.from_dict(
            {
                "host": "api.example.com",
                "domain": "my-domain",
                "api_version": "v1",
                "users": 1,
                "interval_s": 0.1,
                "random_delay_min_s": 0.0,
                "random_delay_max_s": 0.0,
                "duration_s": 0.25,
                "warmup_s": 0.0,
                "ramp_up_s": 0,
                "summary_interval_s": 1,
                "radius_m": 5000,
                "request": {
                    "method": "GET",
                    "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages?lat={{RANDOM_LAT}}&lng={{RANDOM_LNG}}&radius={{RADIUS}}",
                    "timeout_s": 2,
                    "total_timeout_s": 0.05,
                    "headers": {},
                },
                "geo": {
                    "area": "Turin",
                    "named_areas": {
                        "Turin": {
                            "min_lat": 45.0,
                            "max_lat": 45.1,
                            "min_lng": 7.6,
                            "max_lng": 7.7,
                        }
                    },
                },
                "export": {},
            }
        )

        snapshot, _elapsed = asyncio.run(LoadSimulator(config).run())
        assert snapshot.total_requests_sent >= 1
        assert snapshot.timed_out_requests >= 1
        assert snapshot.total_responses_received == 0
        assert snapshot.avg_response_ms == 0.0
        assert snapshot.min_response_ms == 0.0
        assert snapshot.max_response_ms == 0.0
        assert snapshot.p50_response_ms == 0.0
        assert snapshot.p95_response_ms == 0.0
        assert snapshot.p99_response_ms == 0.0
    finally:
        httpx.AsyncClient = original_client
