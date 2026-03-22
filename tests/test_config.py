from simulator.config import LoadTestConfig


def _base_payload() -> dict:
    return {
        "host": "api.example.com",
        "domain": "my-domain",
        "api_version": "v1",
        "users": 1,
        "interval_s": 1,
        "duration_s": 10,
        "ramp_up_s": 0,
        "summary_interval_s": 1,
        "radius_m": 5000,
        "request": {
            "method": "GET",
            "url_template": "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages",
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


def test_random_delay_defaults_to_zero() -> None:
    cfg = LoadTestConfig.from_dict(_base_payload())
    assert cfg.random_delay_min_s == 0.0
    assert cfg.random_delay_max_s == 0.0


def test_random_delay_bounds_validation() -> None:
    payload = _base_payload()
    payload["random_delay_min_s"] = 1.5
    payload["random_delay_max_s"] = 1.0

    try:
        LoadTestConfig.from_dict(payload)
    except ValueError as exc:
        assert "random_delay_min_s must be <= random_delay_max_s" in str(exc)
    else:
        raise AssertionError("ValueError not raised for invalid random delay bounds")


def test_failure_statuses_default() -> None:
    cfg = LoadTestConfig.from_dict(_base_payload())
    assert cfg.failure_statuses == ("4xx", "5xx")


def test_failure_statuses_custom_values() -> None:
    payload = _base_payload()
    payload["failure_statuses"] = ["429", "5xx"]
    cfg = LoadTestConfig.from_dict(payload)
    assert cfg.failure_statuses == ("429", "5xx")


def test_failure_statuses_invalid_value() -> None:
    payload = _base_payload()
    payload["failure_statuses"] = ["6xx"]
    try:
        LoadTestConfig.from_dict(payload)
    except ValueError as exc:
        assert "invalid failure status" in str(exc)
    else:
        raise AssertionError("ValueError not raised for invalid failure status")
