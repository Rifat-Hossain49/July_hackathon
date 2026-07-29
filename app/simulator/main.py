"""CLI entry point for the M0 deterministic simulator slice.

Usage (from repository root):

    python -m app.simulator --seed 42 --chunk-size 65536 \\
        --out app/simulator/events.jsonl

The CLI writes a deterministic JSONL event log to ``--out`` (stdout if
``-``). It is invoked by the test harness and by the experiment plan.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import events, transfer
from .scenario import build_two_peer_scenario, schedule_full_transfer, all_chunks as _scenario_all_chunks


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shongket M0 deterministic simulator slice.")
    parser.add_argument("--seed", type=int, default=42, help="Synthetic media seed.")
    parser.add_argument("--chunk-size", type=int, default=65536, help="Fixed chunk size in bytes.")
    parser.add_argument("--source-size", type=int, default=200_000, help="Synthetic source payload size in bytes.")
    parser.add_argument("--priority", type=str, default="life_safety", choices=["life_safety", "high", "routine"])
    parser.add_argument("--out", type=Path, default=Path("-"), help="JSONL output path or '-' for stdout.")
    return parser.parse_args(argv)


def run(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    sink = sys.stdout if str(args.out) == "-" else args.out.open("w", encoding="utf-8")
    try:
        logger = events.EventLogger(sink=sink)
        scenario = build_two_peer_scenario(
            seed=args.seed,
            chunk_size=args.chunk_size,
            source_size_bytes=args.source_size,
            priority=args.priority,
        )
        items = schedule_full_transfer(scenario)
        transfer.run_encounter(
            sender=scenario.sender,
            receiver=scenario.receiver,
            logger=logger,
            items=items,
            capsule_payload=scenario.capsule,
            manifest_payload=scenario.manifest,
            chunks=_scenario_all_chunks(scenario),
        )
        logger.flush()
    finally:
        if sink is not sys.stdout:
            sink.close()
    return 0
