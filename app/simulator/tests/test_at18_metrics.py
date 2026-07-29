"""AT-18 -- deterministic metrics generation.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-18, M0 logging / M5+
per-device, S1):

    from the experiments in EXPERIMENT_PLAN.md, harness runs collect
    metrics and metric values are recorded.

Evidence required: metric log per scenario. Traceability: "Metrics
recorded | AT-18 | EXPERIMENT_PLAN.md result-table entries per scenario".

Every assertion below compares a metric against a value computed
independently from the scenario (chunk-plan sizes, store counters, event
ticks). No expected metric value is written as a literal that the
implementation could simply echo back.

Timing is reported in ticks, the simulator's only time base. Four
canonical EXPERIMENT_PLAN.md §4 metrics -- throughput in bytes/second,
peak memory, energy and AI inference latency -- are deliberately not
produced; they appear in ``unmeasured`` with a reason, per DR-EXP-01
("avoid invented numbers").
"""

from __future__ import annotations

import io
import json

from app.simulator import events, metrics, scenario, transfer


def _run(seed: int = 42, chunk_size: int = 65536):
    """Run the canonical full-transfer scenario and return its artefacts."""
    scen = scenario.build_two_peer_scenario(seed=seed, chunk_size=chunk_size)
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)
    logger = events.EventLogger(sink=io.StringIO())
    transfer.run_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        items=items,
        capsule_payload=scen.capsule,
        manifest_payload=scen.manifest,
        chunks=chunks,
    )
    return scen, logger, chunks


def _collect(scen, logger, *, scenario_id="1-sender-1-receiver"):
    return metrics.collect(
        logger,
        scenario_id=scenario_id,
        chunk_bytes=metrics.chunk_byte_map(scen.plans),
        expected_chunks={rep: len(plan.chunks) for rep, plan in scen.plans.items()},
        receiver_store=scen.receiver.store,
        signal_plane_bytes=len(json.dumps(scen.capsule).encode())
        + len(json.dumps(scen.manifest).encode()),
    )


# --- computed totals match independently derived values ----------------------


def test_metrics_match_independently_computed_totals():
    scen, logger, chunks = _run()
    m = _collect(scen, logger)

    # Chunk count and bytes are derived from the chunk plans, not literals.
    expected_bytes = sum(len(c.payload) for c in chunks)
    assert m["chunks_delivered"] == len(chunks)
    assert m["bytes_transferred"] == expected_bytes
    assert m["storage_consumption_bytes"] == scen.receiver.store.used_bytes
    assert m["bytes_transferred"] == scen.receiver.store.recompute_used_bytes()

    # Store counters agree with the event log.
    assert m["store_stats"]["stored"] == len(chunks)
    assert m["chunks_rejected"] == m["store_stats"]["rejected_corruption"]

    # Representation completion is measured, not assumed.
    assert m["representations_expected"] == len(scen.plans)
    assert m["representations_completed"] == len(scen.plans)
    assert m["reconstruction_success_rate_ppm"] == 1_000_000

    # A capsule was delivered, so TTFA exists and precedes bulk completion.
    assert m["ttfa_ticks"] is not None
    assert m["tto_ticks"] is not None
    assert m["ttfa_ticks"] < m["tto_ticks"]
    assert m["capsules_delivered"] == 1
    assert m["manifests_delivered"] == 1


def test_completion_ticks_follow_the_progressive_order():
    """TTFT <= TTP <= TTS <= TTO, measured from real delivery ticks."""
    scen, logger, _chunks = _run()
    m = _collect(scen, logger)

    ordered = [m["ttft_ticks"], m["ttp_ticks"], m["tts_ticks"], m["tto_ticks"]]
    assert all(t is not None for t in ordered)
    assert ordered == sorted(ordered)

    # Each completion tick is one that actually appears in the log.
    delivered_ticks = {
        ev.tick for ev in logger.of_type(events.EventType.CHUNK_DELIVERED)
    }
    for tick in ordered:
        assert tick in delivered_ticks


# --- determinism -------------------------------------------------------------


def test_repeated_identical_runs_produce_identical_metrics():
    serialized = []
    for _ in range(2):
        scen, logger, _chunks = _run()
        serialized.append(metrics.to_json(_collect(scen, logger)))
    assert serialized[0] == serialized[1]


def test_serialization_is_stable_and_canonical():
    scen, logger, _chunks = _run()
    m = _collect(scen, logger)

    encoded = metrics.to_json(m)
    # Sorted keys, no incidental whitespace, round-trips exactly.
    assert encoded == json.dumps(m, sort_keys=True, separators=(",", ":"))
    assert ", " not in encoded
    assert json.loads(encoded) == m
    # Re-serializing the same dict is byte-identical.
    assert metrics.to_json(m) == encoded


def test_metrics_change_when_scenario_inputs_change():
    """Different deterministic inputs must produce different metrics."""
    scen_a, logger_a, _ = _run(chunk_size=65536)
    scen_b, logger_b, _ = _run(chunk_size=16_384)
    m_a = _collect(scen_a, logger_a)
    m_b = _collect(scen_b, logger_b)

    # Smaller chunks mean more chunks for the same bytes.
    assert m_b["chunks_delivered"] > m_a["chunks_delivered"]
    assert metrics.to_json(m_a) != metrics.to_json(m_b)

    # A different seed changes the payload bytes but not their size, so
    # the counts and byte totals are legitimately identical; the object
    # identity is what distinguishes the two runs.
    scen_c, logger_c, _ = _run(seed=7)
    assert scen_c.object_id != scen_a.object_id
    m_c = _collect(scen_c, logger_c)
    assert m_c["object_ids"] == [scen_c.object_id]
    assert m_a["object_ids"] == [scen_a.object_id]
    assert m_c["chunks_delivered"] == m_a["chunks_delivered"]
    assert metrics.to_json(m_c) != metrics.to_json(m_a)


# --- rejected operations are counted accurately ------------------------------


def test_duplicates_are_not_counted_as_newly_transferred_bytes():
    scen = scenario.build_two_peer_scenario(chunk_size=16_384)
    chunks = scen.plans["original"].chunks[:3]
    logger = events.EventLogger(sink=io.StringIO())

    # Deliver three chunks, then re-offer the same three.
    transfer.run_budgeted_ingest(
        sender=scen.sender, receiver=scen.receiver, logger=logger, chunks=chunks
    )
    transfer.run_budgeted_ingest(
        sender=scen.sender, receiver=scen.receiver, logger=logger, chunks=chunks
    )

    m = metrics.collect(
        logger,
        scenario_id="duplicate-injection",
        chunk_bytes=metrics.chunk_byte_map(scen.plans),
        receiver_store=scen.receiver.store,
    )

    unique_bytes = sum(len(c.payload) for c in chunks)
    assert m["chunks_delivered"] == 3
    assert m["chunks_duplicate"] == 3
    # Duplicates counted separately; they do not inflate transferred bytes.
    assert m["bytes_transferred"] == unique_bytes
    assert m["duplicate_bytes_avoided"] == unique_bytes
    assert m["storage_consumption_bytes"] == unique_bytes
    assert m["store_stats"]["duplicate_no_op"] == 3


def test_refusal_counters_reflect_actual_refusals():
    scen = scenario.build_two_peer_scenario(chunk_size=16_384)
    chunks = scen.plans["original"].chunks[:4]
    scen.receiver.store.capacity_bytes = sum(len(c.payload) for c in chunks[:2])
    logger = events.EventLogger(sink=io.StringIO())

    transfer.run_budgeted_ingest(
        sender=scen.sender, receiver=scen.receiver, logger=logger, chunks=chunks
    )

    m = metrics.collect(
        logger,
        scenario_id="storage-budget",
        chunk_bytes=metrics.chunk_byte_map(scen.plans),
        receiver_store=scen.receiver.store,
    )

    assert m["storage_budget_rejections"] == 2
    assert m["chunks_delivered"] == 2
    assert m["store_stats"]["rejected_budget"] == 2
    assert m["bytes_transferred"] == scen.receiver.store.used_bytes


def test_multi_peer_contributor_count_is_measured():
    scen = scenario.build_multi_peer_scenario()
    logger = events.EventLogger(sink=io.StringIO())
    transfer.run_multi_peer_completion(
        receiver=scen.receiver,
        providers=scen.providers,
        logger=logger,
        object_id=scen.object_id,
        representation_id=scen.representation_id,
        chunk_indexes=scen.chunk_indexes,
    )

    m = metrics.collect(
        logger,
        scenario_id="multi-peer-reconstruction",
        chunk_bytes=metrics.chunk_byte_map(scen.base.plans),
        receiver_store=scen.receiver.store,
    )

    assert m["contributing_peer_count"] == 2
    assert m["contributing_peer_ids"] == ["peer-A", "peer-B"]
    assert m["chunks_delivered"] == len(scen.chunk_indexes)
    assert m["fragment_requests"] == len(scen.providers)


# --- honesty about what is not measured --------------------------------------


def test_unmeasured_metrics_are_declared_not_invented():
    scen, logger, _chunks = _run()
    m = _collect(scen, logger)

    assert set(m["unmeasured"]) == {
        "throughput_bytes_per_second",
        "peak_memory_mb",
        "energy_joules",
        "ai_inference_latency_ms",
    }
    # Each carries a reason, and none appears as a real metric value.
    for name, reason in m["unmeasured"].items():
        assert isinstance(reason, str) and reason
        assert name not in m

    # The raw inputs for a later throughput calculation are present.
    assert m["bytes_transferred"] is not None
    assert m["total_ticks"] > 0


def test_byte_metrics_are_omitted_rather_than_guessed():
    """Without real chunk sizes, byte metrics are None, not estimates."""
    scen, logger, _chunks = _run()
    m = metrics.collect(logger, scenario_id="no-sizes")

    assert m["bytes_transferred"] is None
    assert m["duplicate_bytes_avoided"] is None
    assert m["protocol_overhead_ppm"] is None
    # Counters that do not need sizes are still produced.
    assert m["chunks_delivered"] > 0


# --- empty run ---------------------------------------------------------------


def test_empty_run_produces_valid_metrics():
    logger = events.EventLogger(sink=io.StringIO())
    m = metrics.collect(logger, scenario_id="empty")

    assert m["schema"] == "shongket.metrics.v1"
    assert m["scenario_id"] == "empty"
    assert m["event_count"] == 0
    assert m["total_ticks"] == 0
    assert m["chunks_delivered"] == 0
    assert m["ttfa_ticks"] is None
    assert m["tto_ticks"] is None
    assert m["contributing_peer_ids"] == []
    assert m["reconstruction_success_rate_ppm"] is None
    # Still serializes canonically.
    assert json.loads(metrics.to_json(m)) == m


def test_preemption_latency_is_measured_in_ticks():
    scen = scenario.build_two_peer_scenario(chunk_size=16_384)
    logger = events.EventLogger(sink=io.StringIO())
    bulk_items = [
        i
        for i in scenario.schedule_full_transfer(scen)
        if i.chunk_index is not None
    ]
    transfer.run_preemption_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        bulk_items=bulk_items,
        bulk_chunks=scenario.all_chunks(scen),
        critical_capsule_payload=scen.capsule,
        critical_object_id=scen.object_id,
        inject_after_chunks=2,
    )

    m = metrics.collect(logger, scenario_id="critical-preempts-bulk")

    assert m["preemptions"] == 1
    assert m["preemption_latency_ticks"] is not None
    assert m["preemption_latency_ticks"] >= 0

    # Cross-check against the raw ticks in the log.
    preempt = logger.of_type(events.EventType.PREEMPTION_LOGGED)[0]
    capsule_ev = next(
        ev
        for ev in logger.of_type(events.EventType.CAPSULE_DELIVERED)
        if ev.tick >= preempt.tick
    )
    assert m["preemption_latency_ticks"] == capsule_ev.tick - preempt.tick
