# API Traffic Simulator

Python load simulator for exercising an existing deployed API with configurable virtual users, periodic requests, random geo coordinates, and metrics reporting.

## Features

- Async virtual users (`asyncio`) with configurable concurrency.
- Fixed per-user scheduling at a configurable request interval.
- Configurable per-request random delay jitter (`min/max`), total duration, and startup ramp-up.
- URL template placeholders with static and random values.
- Static header support (with template placeholders).
- Named area support (for example `Turin`) mapped to geographic bounding boxes.
- Real-time console summary while the test is running.
- Final report with status distribution and response-time metrics (`avg`, `min`, `max`, `p50`, `p95`, `p99`).
- Optional export to JSON and CSV.

## Project Structure

- `main.py`: entrypoint.
- `simulator/config.py`: configuration parsing and validation.
- `simulator/template.py`: template rendering (`{{PLACEHOLDER}}`).
- `simulator/geo.py`: random coordinate generation.
- `simulator/metrics.py`: thread-safe metrics collection and snapshotting.
- `simulator/simulator.py`: user loops, request dispatch, and execution control.
- `simulator/reporting.py`: realtime/final reporting and export utilities.
- `config.example.toml`: sample config.
- `tests/`: unit and behavior tests.

## Requirements

- Python 3.11+
- Dependencies from `requirements.txt`

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

1. Copy the sample config and customize it:

```bash
cp config.example.toml config.toml
```

2. Start the simulator:

```bash
python main.py --config config.toml
```

## Configuration

Main fields:

- `users`: number of concurrent virtual users.
- `interval_s`: request interval per user in seconds.
- `random_delay_min_s`: minimum random delay added before a scheduled request.
- `random_delay_max_s`: maximum random delay added before a scheduled request.
- `duration_s`: total test duration in seconds.
- `ramp_up_s`: optional startup spread (seconds) to avoid simultaneous start.
- `radius_m`: radius used in the request template.
- `summary_interval_s`: real-time summary print interval.
- `failure_statuses`: status codes/classes counted as failures (default `["4xx", "5xx"]`).
- `client_max_connections`: max connections in shared HTTP pool (default `1000`).
- `client_max_keepalive_connections`: max keepalive connections in pool (default `200`).
- `client_keepalive_expiry_s`: keepalive expiry in seconds (default `30`).
- `client_http2`: enable HTTP/2 when supported by server (default `false`).
- `client_trust_env`: use proxy/SSL settings from environment (default `true`).
- `max_in_flight_requests`: optional global cap for concurrent in-flight requests.
- `request.method`: HTTP method.
- `request.url_template`: URL template with placeholders.
- `request.body_template`: optional request body template (useful for `POST`/`PUT`, supports placeholders).
- `request.headers`: static headers (values can also include placeholders).
- `request.timeout_s`: HTTP timeout.
- `geo.area`: selected named area (for example `Turin`).
- `geo.named_areas.<Name>`: bounding box for random lat/lng generation.
- `export.json_path`: optional output JSON path.
- `export.csv_path`: optional output CSV path.

Supported placeholders:

- `{{HOST}}`
- `{{DOMAIN}}`
- `{{API_VERSION}}`
- `{{RANDOM_LAT}}`
- `{{RANDOM_LNG}}`
- `{{RADIUS}}`

Example `POST` body template:

```toml
[request]
method = "POST"
url_template = "https://{{HOST}}/{{DOMAIN}}/mobile/{{API_VERSION}}/messages"
body_template = '''{"lat":"{{RANDOM_LAT}}","lng":"{{RANDOM_LNG}}","radius":"{{RADIUS}}"}'''
timeout_s = 10
```

## Area Configuration (example: Turin)

To simulate users in Turin, set:

- `geo.area = "Turin"`
- define `geo.named_areas.Turin` with `min_lat`, `max_lat`, `min_lng`, `max_lng`

Coordinates are generated uniformly in the configured bounding box.

Scheduling behavior:

- Each user follows a fixed periodic schedule based on `interval_s`.
- For each scheduled request, an additional random delay in `[random_delay_min_s, random_delay_max_s]` is applied.

High-user tuning notes:

- The simulator uses a single shared `httpx.AsyncClient` and connection pool to reduce client overhead.
- For very high user counts, set `max_in_flight_requests` to prevent local machine saturation.
- Tune `client_max_connections` and `client_max_keepalive_connections` according to target load and machine capacity.

## Testing

Run:

```bash
pytest
```

The tests cover template rendering, geo sampling, metrics aggregation, and simulator request behavior (including header injection).
