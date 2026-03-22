from __future__ import annotations

import asyncio
import random
import time

import httpx

from simulator.config import LoadTestConfig
from simulator.geo import GeoSampler
from simulator.metrics import MetricsCollector, MetricsSnapshot
from simulator.reporting import render_realtime_progress, render_warmup_progress
from simulator.template import render_template


class LoadSimulator:
    def __init__(self, config: LoadTestConfig) -> None:
        self._config = config
        self._metrics = MetricsCollector()
        self._bounds = config.geo.resolve_bounds()
        self._in_flight_limiter = (
            asyncio.Semaphore(config.max_in_flight_requests) if config.max_in_flight_requests is not None else None
        )

    async def run(self, stop_event: asyncio.Event | None = None) -> tuple[MetricsSnapshot, float]:
        if stop_event is None:
            stop_event = asyncio.Event()

        run_start = time.perf_counter()
        measurement_start = run_start + self._config.warmup_s
        end_time = measurement_start + self._config.duration_s
        limits = httpx.Limits(
            max_connections=self._config.client_max_connections,
            max_keepalive_connections=self._config.client_max_keepalive_connections,
            keepalive_expiry=self._config.client_keepalive_expiry_s,
        )
        timeout = httpx.Timeout(
            connect=self._config.request.connect_timeout_s,
            read=self._config.request.read_timeout_s,
            write=self._config.request.write_timeout_s,
            pool=self._config.request.pool_timeout_s,
        )
        client_kwargs = {
            "timeout": timeout,
            "follow_redirects": True,
            "limits": limits,
            "http2": self._config.client_http2,
            "trust_env": self._config.client_trust_env,
        }

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                await self._execute_users(run_start, measurement_start, end_time, stop_event, client)
        except ImportError as exc:
            if self._config.client_http2 and "h2" in str(exc).lower():
                print("HTTP/2 requested but 'h2' is not installed; falling back to HTTP/1.1.")
                client_kwargs["http2"] = False
                async with httpx.AsyncClient(**client_kwargs) as client:
                    await self._execute_users(run_start, measurement_start, end_time, stop_event, client)
            else:
                raise

        elapsed_s = max(time.perf_counter() - measurement_start, 0.0)
        snapshot = self._metrics.snapshot()
        return snapshot, elapsed_s

    async def _execute_users(
        self,
        run_start: float,
        measurement_start: float,
        end_time: float,
        stop_event: asyncio.Event,
        client: httpx.AsyncClient,
    ) -> None:
        users = [
            asyncio.create_task(
                self._run_user(user_id, measurement_start, end_time, stop_event, client), name=f"user-{user_id}"
            )
            for user_id in range(self._config.users)
        ]
        summary_task = asyncio.create_task(
            self._emit_realtime_summary(run_start, measurement_start, end_time, stop_event),
            name="summary",
        )

        await asyncio.gather(*users)
        summary_task.cancel()
        try:
            await summary_task
        except asyncio.CancelledError:
            pass

    async def _run_user(
        self,
        user_id: int,
        measurement_start: float,
        end_time: float,
        stop_event: asyncio.Event,
        client: httpx.AsyncClient,
    ) -> None:
        ramp_offset_s = self._compute_ramp_offset(user_id)
        user_start_s = time.perf_counter()
        if ramp_offset_s > 0:
            should_stop = await self._sleep_or_stop(ramp_offset_s, stop_event)
            if should_stop:
                return
            user_start_s += ramp_offset_s

        sampler = GeoSampler(self._bounds, seed=_seed_for_user(self._config.random_seed, user_id))
        jitter_rng = random.Random(_seed_for_user(self._config.random_seed, user_id + 100_000))
        next_scheduled_s = user_start_s
        while True:
            if stop_event.is_set():
                break
            if time.perf_counter() >= end_time:
                break
            jitter_s = jitter_rng.uniform(
                self._config.random_delay_min_s,
                self._config.random_delay_max_s,
            )
            target_s = next_scheduled_s + jitter_s
            now_s = time.perf_counter()
            if target_s > end_time:
                break
            if target_s > now_s:
                should_stop = await self._sleep_or_stop(target_s - now_s, stop_event)
                if should_stop:
                    break
            if time.perf_counter() >= end_time:
                break

            is_measured = time.perf_counter() >= measurement_start
            if is_measured:
                self._metrics.record_request_sent()
            point = sampler.sample()
            values = {
                "HOST": self._config.host,
                "DOMAIN": self._config.domain,
                "API_VERSION": self._config.api_version,
                "RANDOM_LAT": f"{point.lat:.6f}",
                "RANDOM_LNG": f"{point.lng:.6f}",
                "RADIUS": str(self._config.radius_m),
            }
            url = render_template(self._config.request.url_template, values)
            body = (
                render_template(self._config.request.body_template, values)
                if self._config.request.body_template is not None
                else None
            )
            headers = {k: render_template(v, values) for k, v in self._config.request.headers.items()}
            started = 0.0

            try:
                if self._in_flight_limiter is None:
                    started = time.perf_counter()
                    response = await client.request(self._config.request.method, url, headers=headers, content=body)
                else:
                    async with self._in_flight_limiter:
                        started = time.perf_counter()
                        response = await client.request(
                            self._config.request.method, url, headers=headers, content=body
                        )
            except httpx.TimeoutException:
                if is_measured:
                    self._metrics.record_timeout()
            except Exception:
                if is_measured:
                    self._metrics.record_failure()
            else:
                if is_measured:
                    elapsed_s = time.perf_counter() - started
                    self._metrics.record_response(
                        response.status_code,
                        elapsed_s,
                        response.headers.get("content-type"),
                        is_failure=self._is_failure_status(response.status_code),
                    )
            next_scheduled_s += self._config.interval_s

    async def _emit_realtime_summary(
        self, run_start: float, measurement_start: float, end_time: float, stop_event: asyncio.Event
    ) -> None:
        refresh_s = min(self._config.summary_interval_s, 0.25)
        previous_length = 0
        try:
            while True:
                now_s = time.perf_counter()
                active_users = self._active_users_at_elapsed(max(now_s - run_start, 0.0))
                if now_s < measurement_start:
                    warmup_elapsed_s = max(now_s - run_start, 0.0)
                    line = render_warmup_progress(
                        elapsed_s=warmup_elapsed_s,
                        warmup_s=self._config.warmup_s,
                        active_users=active_users,
                        total_users=self._config.users,
                    )
                else:
                    elapsed_s = min(now_s - measurement_start, self._config.duration_s)
                    elapsed_s = max(elapsed_s, 0.0)
                    snapshot = self._metrics.snapshot()
                    line = render_realtime_progress(
                        snapshot=snapshot,
                        elapsed_s=elapsed_s,
                        duration_s=self._config.duration_s,
                        active_users=active_users,
                        total_users=self._config.users,
                    )
                padding = " " * max(previous_length - len(line), 0)
                print(f"\r{line}{padding}", end="", flush=True)
                previous_length = len(line)

                if now_s >= end_time or stop_event.is_set():
                    break
                should_stop = await self._sleep_or_stop(refresh_s, stop_event)
                if should_stop:
                    break
        finally:
            if previous_length > 0:
                print()

    def _active_users_at_elapsed(self, elapsed_s: float) -> int:
        if self._config.users <= 1 or self._config.ramp_up_s <= 0:
            return self._config.users

        slot = self._config.ramp_up_s / max(self._config.users - 1, 1)
        if slot <= 0:
            return self._config.users

        started_users = int(elapsed_s / slot) + 1
        return min(self._config.users, max(started_users, 1))

    def _compute_ramp_offset(self, user_id: int) -> float:
        if self._config.ramp_up_s <= 0 or self._config.users == 1:
            return 0.0
        slot = self._config.ramp_up_s / max(self._config.users - 1, 1)
        return slot * user_id

    async def _sleep_or_stop(self, duration_s: float, stop_event: asyncio.Event) -> bool:
        if duration_s <= 0:
            return stop_event.is_set()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=duration_s)
            return True
        except asyncio.TimeoutError:
            return False

    def _is_failure_status(self, status_code: int) -> bool:
        status_code_str = str(status_code)
        status_class = f"{status_code // 100}xx"
        return status_code_str in self._config.failure_statuses or status_class in self._config.failure_statuses


def _seed_for_user(base_seed: int | None, user_id: int) -> int | None:
    if base_seed is None:
        return None
    return base_seed + user_id
