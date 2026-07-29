"""Deterministic metrics collection (M0 -- AT-18).

Every value produced here is *computed* from something the simulator
actually did:

* the structured event log (``events.EventLogger``);
* store counters (``store.ContentAddressedStore.stats`` / ``quota``);
* the chunk plans that describe real payload sizes;
* deterministic simulator ticks.

Nothing is hard-coded, sampled, estimated or timed against a wall clock.
Running the same scenario twice yields byte-identical serialized output.

Canonical metric set
--------------------

EXPERIMENT_PLAN.md §4 lists fifteen M0 metrics. Four of them cannot be
produced honestly by a deterministic in-process simulator, so they are
reported in ``unmeasured`` with a reason rather than filled with an
invented number. That follows DR-EXP-01 ("result tables are filled by
the harness's logs only ... avoid invented numbers") and AGENTS.md's ban
on claims that exceed measurement:

* **Throughput (local bytes/second)** -- the simulator has no wall-clock
  time base, and inventing one would fabricate a performance claim. The
  raw inputs a reader needs (``bytes_transferred``, ``total_ticks``) are
  both reported; a bytes-per-second figure requires a real device (M3+).
* **Peak memory (MB)** -- requires process instrumentation outside the
  standard-library simulator.
* **Energy use (Joules)** -- requires device measurement (M3+).
* **AI inference latency (ms)** -- EXPERIMENT_PLAN.md §4 already records
  this as "manual form in M0; measured only when M6 enabled". M0 runs no
  model at all (AT-15).

Timing metrics are reported in **ticks**, the simulator's only time
base, and are named ``*_ticks`` so they can never be mistaken for
milliseconds. EXPERIMENT_PLAN.md §4 defines TTFA/TTFT/TTP/TTS/TTO and
preemption latency in time units; on real devices (M3+) those become
wall-clock figures, and the tick values here are the M0 stand-in.
"""

from __future__ import annotations

import json

from . import events


# Representation -> the EXPERIMENT_PLAN §4 metric name for its completion.
_REPRESENTATION_METRIC: dict[str, str] = {
    "thumb": "ttft_ticks",
    "preview": "ttp_ticks",
    "standard": "tts_ticks",
    "original": "tto_ticks",
}

UNMEASURED: dict[str, str] = {
    "throughput_bytes_per_second": (
        "no wall-clock time base in the M0 simulator; see bytes_transferred "
        "and total_ticks"
    ),
    "peak_memory_mb": "requires process instrumentation; measured from M3+",
    "energy_joules": "requires device measurement; measured from M3+",
    "ai_inference_latency_ms": (
        "M0 uses the manual form and runs no model (AT-15); measured only "
        "when M6 is enabled"
    ),
}


def _ratio_ppm(numerator: int, denominator: int) -> int | None:
    """Return ``numerator / denominator`` in parts per million.

    Integer parts-per-million keeps the serialized output byte-stable
    without depending on float repr. ``None`` when undefined.
    """
    if denominator <= 0:
        return None
    return round(numerator * 1_000_000 / denominator)


def collect(
    logger: events.EventLogger,
    *,
    scenario_id: str,
    chunk_bytes: dict[tuple[str, str, int], int] | None = None,
    expected_chunks: dict[str, int] | None = None,
    receiver_store=None,
    signal_plane_bytes: int = 0,
) -> dict:
    """Compute the M0 metric set for one harness run.

    Parameters
    ----------
    logger:
        The event log the run produced. This is the primary source.
    scenario_id:
        Label for the EXPERIMENT_PLAN.md result-table row.
    chunk_bytes:
        Real payload sizes keyed by
        ``(object_id, representation_id, chunk_index)``, taken from the
        scenario's chunk plans. Byte metrics are omitted when absent
        rather than guessed -- the event log deliberately does not carry
        payload sizes, and widening it just to simplify metrics would
        change existing event semantics.
    expected_chunks:
        ``representation_id -> chunk count`` for the object under test.
        Drives the completion-tick metrics and the reconstruction rate.
    receiver_store:
        Optional ``ContentAddressedStore`` for storage-consumption and
        rejection counters.
    signal_plane_bytes:
        Serialized capsule + manifest bytes actually sent, used for the
        protocol-overhead ratio.
    """
    evs = logger.events
    by_type: dict[events.EventType, list] = {}
    for ev in evs:
        by_type.setdefault(ev.type, []).append(ev)

    def count(t: events.EventType) -> int:
        return len(by_type.get(t, []))

    def first_tick(t: events.EventType) -> int | None:
        found = by_type.get(t)
        return found[0].tick if found else None

    delivered = by_type.get(events.EventType.CHUNK_DELIVERED, [])
    duplicates = by_type.get(events.EventType.CHUNK_DUPLICATE, [])

    # --- byte accounting, from real chunk sizes ----------------------------
    bytes_transferred: int | None = None
    duplicate_bytes_avoided: int | None = None
    if chunk_bytes is not None:
        bytes_transferred = sum(
            chunk_bytes.get(
                (ev.object_id, ev.representation_id, ev.chunk_index), 0
            )
            for ev in delivered
        )
        duplicate_bytes_avoided = sum(
            chunk_bytes.get(
                (ev.object_id, ev.representation_id, ev.chunk_index), 0
            )
            for ev in duplicates
        )

    # --- completion ticks per representation -------------------------------
    completion: dict[str, int | None] = {
        name: None for name in _REPRESENTATION_METRIC.values()
    }
    representations_completed = 0
    representations_expected = 0
    if expected_chunks:
        representations_expected = len(expected_chunks)
        seen: dict[str, set[int]] = {rep: set() for rep in expected_chunks}
        for ev in delivered:
            rep = ev.representation_id
            if rep not in seen or ev.chunk_index is None:
                continue
            if rep in seen and len(seen[rep]) == expected_chunks[rep]:
                continue
            seen[rep].add(ev.chunk_index)
            if len(seen[rep]) == expected_chunks[rep]:
                metric = _REPRESENTATION_METRIC.get(rep)
                if metric is not None:
                    completion[metric] = ev.tick
                representations_completed += 1

    # --- preemption latency, in ticks --------------------------------------
    preemption_latency_ticks: int | None = None
    preempt_tick = first_tick(events.EventType.PREEMPTION_LOGGED)
    if preempt_tick is not None:
        for ev in by_type.get(events.EventType.CAPSULE_DELIVERED, []):
            if ev.tick >= preempt_tick:
                preemption_latency_ticks = ev.tick - preempt_tick
                break

    ticks = [ev.tick for ev in evs]
    total_ticks = (max(ticks) - min(ticks)) if ticks else 0

    contributing_peers = sorted({ev.sender_id for ev in delivered})

    # Identify the objects these metrics describe, read back out of the
    # log. Without this a result-table row cannot be traced to what was
    # measured: two runs over different source media of the same size
    # produce identical counts and byte totals.
    object_ids = sorted({ev.object_id for ev in evs if ev.object_id})

    metrics: dict = {
        "schema": "shongket.metrics.v1",
        "scenario_id": scenario_id,
        "object_ids": object_ids,
        # --- timing (ticks; the simulator's only time base) ---------------
        "ttfa_ticks": first_tick(events.EventType.CAPSULE_DELIVERED),
        "ttft_ticks": completion["ttft_ticks"],
        "ttp_ticks": completion["ttp_ticks"],
        "tts_ticks": completion["tts_ticks"],
        "tto_ticks": completion["tto_ticks"],
        "preemption_latency_ticks": preemption_latency_ticks,
        "total_ticks": total_ticks,
        "event_count": len(evs),
        # --- transfer counters --------------------------------------------
        "capsules_delivered": count(events.EventType.CAPSULE_DELIVERED),
        "capsules_rejected": count(events.EventType.CAPSULE_REJECTED),
        "manifests_delivered": count(events.EventType.MANIFEST_DELIVERED),
        "chunks_delivered": len(delivered),
        "chunks_duplicate": len(duplicates),
        "chunks_rejected": count(events.EventType.CHUNK_REJECTED),
        "encounters_opened": count(events.EventType.ENCOUNTER_OPENED),
        "preemptions": count(events.EventType.PREEMPTION_LOGGED),
        "interruptions": count(events.EventType.TRANSFER_INTERRUPTED),
        "resumes": count(events.EventType.TRANSFER_RESUMED),
        "restarts": count(events.EventType.RESTART_COMPLETED),
        "fragment_requests": count(events.EventType.FRAGMENT_REQUESTED),
        # --- refusal counters (AT-11/12/15/16/17) -------------------------
        "expired_forward_refusals": count(events.EventType.FORWARD_REFUSED),
        "storage_budget_rejections": count(
            events.EventType.STORAGE_BUDGET_REJECTED
        ),
        "model_fallbacks": count(events.EventType.MODEL_FALLBACK),
        "consent_rejections": count(events.EventType.CONSENT_REJECTED),
        "oversized_payload_rejections": count(
            events.EventType.PAYLOAD_REJECTED
        ),
        # --- multi-peer (AT-08) -------------------------------------------
        "contributing_peer_ids": contributing_peers,
        "contributing_peer_count": len(contributing_peers),
        # --- bytes ---------------------------------------------------------
        "bytes_transferred": bytes_transferred,
        "duplicate_bytes_avoided": duplicate_bytes_avoided,
        "signal_plane_bytes": signal_plane_bytes,
        # --- reconstruction -------------------------------------------------
        "representations_completed": representations_completed,
        "representations_expected": representations_expected,
        "reconstruction_success_rate_ppm": _ratio_ppm(
            representations_completed, representations_expected
        ),
        "unmeasured": dict(UNMEASURED),
    }

    if bytes_transferred is not None:
        total_bytes = bytes_transferred + signal_plane_bytes
        metrics["protocol_overhead_ppm"] = _ratio_ppm(
            signal_plane_bytes, total_bytes
        )
    else:
        metrics["protocol_overhead_ppm"] = None

    if receiver_store is not None:
        metrics["storage_consumption_bytes"] = receiver_store.used_bytes
        metrics["store_stats"] = receiver_store.stats.as_dict()
        metrics["store_quota"] = receiver_store.quota()

    return metrics


def to_json(metrics: dict) -> str:
    """Serialize metrics canonically: sorted keys, no incidental spacing."""
    return json.dumps(metrics, sort_keys=True, separators=(",", ":"))


def chunk_byte_map(plans: dict) -> dict[tuple[str, str, int], int]:
    """Build the ``chunk_bytes`` map from a scenario's chunk plans.

    Sizes come from the actual fragmented payloads, so byte metrics are
    measurements rather than assumptions.
    """
    sizes: dict[tuple[str, str, int], int] = {}
    for plan in plans.values():
        for chunk in plan.chunks:
            key = (chunk.object_id, chunk.representation_id, chunk.chunk_index)
            sizes[key] = len(chunk.payload)
    return sizes
