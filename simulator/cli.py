from __future__ import annotations

import argparse
import asyncio
import signal

from simulator.config import LoadTestConfig
from simulator.reporting import export_csv, export_json, render_final_report
from simulator.simulator import LoadSimulator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="API load simulator")
    parser.add_argument("--config", required=True, help="Path to TOML config file")
    return parser.parse_args()


async def run_from_config(config_path: str) -> int:
    config = LoadTestConfig.from_toml(config_path)
    simulator = LoadSimulator(config)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    interrupted = False
    previous_sigint_handler = signal.getsignal(signal.SIGINT)

    def _on_sigint(_signum: int, _frame: object) -> None:
        nonlocal interrupted
        interrupted = True
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGINT, _on_sigint)
    try:
        snapshot, elapsed_s = await simulator.run(stop_event=stop_event)
    finally:
        signal.signal(signal.SIGINT, previous_sigint_handler)

    if interrupted:
        print("Interrupted by user (Ctrl-C). Final partial report:")

    print(
        render_final_report(
            snapshot,
            elapsed_s,
            tested_url=config.request.url_template,
            emulated_users=config.users,
        )
    )

    if config.export_json:
        export_json(config.export_json, snapshot, elapsed_s)
        print(f"JSON report exported to {config.export_json}")
    if config.export_csv:
        export_csv(config.export_csv, snapshot, elapsed_s)
        print(f"CSV report exported to {config.export_csv}")

    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_from_config(args.config))


if __name__ == "__main__":
    raise SystemExit(main())
