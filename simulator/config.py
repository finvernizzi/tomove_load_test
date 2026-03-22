from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class GeoBounds:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def validate(self) -> None:
        if self.min_lat >= self.max_lat:
            raise ValueError("geo bounds invalid: min_lat must be < max_lat")
        if self.min_lng >= self.max_lng:
            raise ValueError("geo bounds invalid: min_lng must be < max_lng")


@dataclass(frozen=True)
class GeoConfig:
    area: str
    named_areas: dict[str, GeoBounds]

    def resolve_bounds(self) -> GeoBounds:
        key = self.area.strip().lower()
        for name, bounds in self.named_areas.items():
            if name.strip().lower() == key:
                bounds.validate()
                return bounds
        available = ", ".join(sorted(self.named_areas.keys()))
        raise ValueError(f"unknown geo area '{self.area}'. Available areas: {available}")


@dataclass(frozen=True)
class RequestConfig:
    method: str
    url_template: str
    body_template: str | None
    headers: dict[str, str]
    timeout_s: float
    connect_timeout_s: float
    read_timeout_s: float
    write_timeout_s: float
    pool_timeout_s: float
    total_timeout_s: float


@dataclass(frozen=True)
class LoadTestConfig:
    host: str
    domain: str
    api_version: str
    users: int
    interval_s: float
    random_delay_min_s: float
    random_delay_max_s: float
    duration_s: float
    warmup_s: float
    ramp_up_s: float
    summary_interval_s: float
    radius_m: int
    request: RequestConfig
    geo: GeoConfig
    export_json: str | None
    export_csv: str | None
    random_seed: int | None
    failure_statuses: tuple[str, ...]
    client_max_connections: int
    client_max_keepalive_connections: int
    client_keepalive_expiry_s: float
    client_http2: bool
    client_trust_env: bool
    max_in_flight_requests: int | None

    @classmethod
    def from_toml(cls, path: str | Path) -> "LoadTestConfig":
        parsed = tomllib.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(parsed)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "LoadTestConfig":
        request_payload = payload["request"]
        geo_payload = payload["geo"]

        named_areas: dict[str, GeoBounds] = {}
        for area_name, bounds in geo_payload["named_areas"].items():
            named_areas[area_name] = GeoBounds(
                min_lat=float(bounds["min_lat"]),
                max_lat=float(bounds["max_lat"]),
                min_lng=float(bounds["min_lng"]),
                max_lng=float(bounds["max_lng"]),
            )

        config = cls(
            host=str(payload["host"]),
            domain=str(payload["domain"]),
            api_version=str(payload["api_version"]),
            users=int(payload["users"]),
            interval_s=float(payload["interval_s"]),
            random_delay_min_s=float(payload.get("random_delay_min_s", 0.0)),
            random_delay_max_s=float(payload.get("random_delay_max_s", 0.0)),
            duration_s=float(payload["duration_s"]),
            warmup_s=float(payload.get("warmup_s", 0.0)),
            ramp_up_s=float(payload.get("ramp_up_s", 0.0)),
            summary_interval_s=float(payload.get("summary_interval_s", 5.0)),
            radius_m=int(payload.get("radius_m", 5000)),
            request=RequestConfig(
                method=str(request_payload.get("method", "GET")).upper(),
                url_template=str(request_payload["url_template"]),
                body_template=(
                    str(request_payload["body_template"]) if request_payload.get("body_template") is not None else None
                ),
                headers={str(k): str(v) for k, v in request_payload.get("headers", {}).items()},
                timeout_s=float(request_payload.get("timeout_s", 10.0)),
                connect_timeout_s=float(request_payload.get("connect_timeout_s", request_payload.get("timeout_s", 10.0))),
                read_timeout_s=float(request_payload.get("read_timeout_s", request_payload.get("timeout_s", 10.0))),
                write_timeout_s=float(request_payload.get("write_timeout_s", request_payload.get("timeout_s", 10.0))),
                pool_timeout_s=float(request_payload.get("pool_timeout_s", request_payload.get("timeout_s", 10.0))),
                total_timeout_s=float(request_payload.get("total_timeout_s", request_payload.get("timeout_s", 10.0))),
            ),
            geo=GeoConfig(
                area=str(geo_payload["area"]),
                named_areas=named_areas,
            ),
            export_json=payload.get("export", {}).get("json_path"),
            export_csv=payload.get("export", {}).get("csv_path"),
            random_seed=payload.get("random_seed"),
            failure_statuses=_parse_failure_statuses(payload.get("failure_statuses", ["4xx", "5xx"])),
            client_max_connections=int(payload.get("client_max_connections", 1000)),
            client_max_keepalive_connections=int(payload.get("client_max_keepalive_connections", 200)),
            client_keepalive_expiry_s=float(payload.get("client_keepalive_expiry_s", 30.0)),
            client_http2=bool(payload.get("client_http2", False)),
            client_trust_env=bool(payload.get("client_trust_env", True)),
            max_in_flight_requests=(
                int(payload["max_in_flight_requests"]) if payload.get("max_in_flight_requests") is not None else None
            ),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.users <= 0:
            raise ValueError("users must be > 0")
        if self.interval_s <= 0:
            raise ValueError("interval_s must be > 0")
        if self.random_delay_min_s < 0:
            raise ValueError("random_delay_min_s must be >= 0")
        if self.random_delay_max_s < 0:
            raise ValueError("random_delay_max_s must be >= 0")
        if self.random_delay_min_s > self.random_delay_max_s:
            raise ValueError("random_delay_min_s must be <= random_delay_max_s")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be > 0")
        if self.warmup_s < 0:
            raise ValueError("warmup_s must be >= 0")
        if self.ramp_up_s < 0:
            raise ValueError("ramp_up_s must be >= 0")
        if self.summary_interval_s <= 0:
            raise ValueError("summary_interval_s must be > 0")
        if self.radius_m <= 0:
            raise ValueError("radius_m must be > 0")
        if self.request.timeout_s <= 0:
            raise ValueError("request.timeout_s must be > 0")
        if self.request.connect_timeout_s <= 0:
            raise ValueError("request.connect_timeout_s must be > 0")
        if self.request.read_timeout_s <= 0:
            raise ValueError("request.read_timeout_s must be > 0")
        if self.request.write_timeout_s <= 0:
            raise ValueError("request.write_timeout_s must be > 0")
        if self.request.pool_timeout_s <= 0:
            raise ValueError("request.pool_timeout_s must be > 0")
        if self.request.total_timeout_s <= 0:
            raise ValueError("request.total_timeout_s must be > 0")
        if self.client_max_connections <= 0:
            raise ValueError("client_max_connections must be > 0")
        if self.client_max_keepalive_connections < 0:
            raise ValueError("client_max_keepalive_connections must be >= 0")
        if self.client_max_keepalive_connections > self.client_max_connections:
            raise ValueError("client_max_keepalive_connections must be <= client_max_connections")
        if self.client_keepalive_expiry_s <= 0:
            raise ValueError("client_keepalive_expiry_s must be > 0")
        if self.max_in_flight_requests is not None and self.max_in_flight_requests <= 0:
            raise ValueError("max_in_flight_requests must be > 0 when provided")
        if not self.request.url_template:
            raise ValueError("request.url_template is required")
        self.geo.resolve_bounds()


_FAILURE_STATUS_PATTERN = re.compile(r"^[1-5](?:xx|[0-9]{2})$")


def _parse_failure_statuses(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list) or not values:
        raise ValueError("failure_statuses must be a non-empty list (for example ['4xx', '5xx'])")

    normalized: list[str] = []
    for raw in values:
        value = str(raw).strip().lower()
        if not _FAILURE_STATUS_PATTERN.match(value):
            raise ValueError(
                f"invalid failure status '{raw}'. Use HTTP codes like 404 or classes like 4xx/5xx."
            )
        normalized.append(value)

    return tuple(normalized)
