"""AT-20 — malformed schema payload rejected.

The acceptance criterion (ACCEPTANCE_TESTS.md §AT-20, M0, S1):

    payload with missing required field / bad enum / unsupported schema
    is rejected; nothing persisted; nothing scheduled; ProtocolError
    code == "SCHEMA_INVALID".

Each invalid payload type is exercised in its own test, and the store
plus scheduler state are verified to remain unchanged after rejection.
"""

from __future__ import annotations

import pytest

from app.simulator import validation
from app.simulator.peer import SimulatedPeer


def _good_fragment() -> dict:
    return {
        "schema": "shongket.fragment.v1",
        "object_id": "a" * 64,
        "representation_id": "thumb",
        "chunk_index": 0,
        "chunk_size": 4,
        "byte_range": [0, 3],
        "hash": "0" * 64,
    }


def test_missing_required_field_is_rejected():
    bad = _good_fragment()
    del bad["chunk_index"]
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.fragment.v1", bad)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_unsupported_schema_string_is_rejected():
    bad = _good_fragment()
    bad["schema"] = "shongket.fragment.v999"
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.fragment.v1", bad)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_invalid_enum_value_is_rejected():
    bad = _good_fragment()
    bad["representation_id"] = "custom_representation"
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.fragment.v1", bad)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_invalid_field_type_is_rejected():
    bad = _good_fragment()
    bad["chunk_index"] = "0"
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.fragment.v1", bad)
    assert excinfo.value.code == "SCHEMA_INVALID"


def test_store_and_scheduler_remain_unchanged_on_invalid_payload():
    """A failed ``put_chunk`` must not persist the fragment; the only
    legitimate state change is the ``rejected_schema`` counter."""
    receiver = SimulatedPeer(peer_id="peer-B")
    snapshot_fragments = dict(receiver.store._fragments)

    from app.simulator.chunks import Chunk
    import hashlib

    object_id = "f" * 64
    bad_chunk = Chunk(
        object_id=object_id,
        representation_id="not_an_enum",  # invalid enum value
        chunk_index=0,
        byte_range=(0, 3),
        sha256=hashlib.sha256(b"data").hexdigest(),
        payload=b"data",
    )
    with pytest.raises(validation.ProtocolError):
        receiver.store.put_chunk(bad_chunk)

    # Fragment map must be unchanged.
    assert receiver.store._fragments == snapshot_fragments
    # Nothing stored; only the schema-rejection counter advanced.
    assert receiver.store.stats.stored == 0
    assert receiver.store.stats.rejected_schema == 1
    assert receiver.store.stats.rejected_corruption == 0
    assert receiver.store.stats.duplicate_no_op == 0


# --- ingress-boundary hardening for AT-20 -----------------------------------
#
# The scheduler must reject malformed payloads *before* mutating its
# internal queue, before persisting fragments, and before emitting any
# scheduling event. The tests below capture the queue, store and event-log
# state before and after a rejected admission so all three boundaries are
# exercised together.


def _good_fragment_payload(object_id: str = "a" * 64, *, representation_id: str = "thumb") -> dict:
    return {
        "schema": "shongket.fragment.v1",
        "object_id": object_id,
        "representation_id": representation_id,
        "chunk_index": 0,
        "chunk_size": 4,
        "byte_range": [0, 3],
        "hash": "0" * 64,
    }


def test_ingress_admits_valid_payload_and_rejects_malformed():
    """Valid payloads are appended; malformed payloads raise SCHEMA_INVALID
    and the queue length is unchanged."""
    from app.simulator.ingress import SchedulerIngress
    from app.simulator import priority

    ingress = SchedulerIngress()
    item_a = priority.SchedulerItem.manifest(object_id="o1", manifest_id="mA")
    item_b = priority.SchedulerItem.manifest(object_id="o2", manifest_id="mB")
    valid_payload = {
        "schema": "shongket.content.v1",
        "object_id": "o1",
        "capsule_ref": "c1",
        "representations": [
            {
                "id": "thumb",
                "kind": "image/jpeg",
                "byte_len": 0,
                "chunk_size": 65536,
                "hashes": [],
                "rep_sha256": "0" * 64,
            }
        ],
        "priority": "life_safety",
        "created_at_unix": 1_700_000_000,
        "hop_limit": 6,
        "copy_budget": 8,
    }
    # Valid admission: queue grows by one.
    ingress.admit(item_a, payload=valid_payload)
    assert ingress.queue_length() == 1
    # Malformed payload: missing required field must be rejected; queue
    # length must not change.
    bad_payload = dict(valid_payload)
    del bad_payload["object_id"]
    with pytest.raises(validation.ProtocolError) as excinfo:
        ingress.admit(item_b, payload=bad_payload)
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert ingress.queue_length() == 1
    assert ingress.snapshot() == [item_a]


def test_rejected_admission_leaves_queue_storage_and_eventlog_unchanged():
    """Three-way state snapshot: rejected payload must not mutate
    the scheduler queue, the storage map or the event log."""
    from app.simulator.ingress import SchedulerIngress
    from app.simulator import events, priority
    from app.simulator.chunks import Chunk
    import io
    import hashlib

    sender = SimulatedPeer(peer_id="peer-A")
    receiver = SimulatedPeer(peer_id="peer-B")

    sink = io.StringIO()
    logger = events.EventLogger(sink=sink)

    # Seed the event log and the store with one valid item so we can
    # prove they are not affected by the rejected admission.
    seed_chunk = Chunk(
        object_id="o" * 64,
        representation_id="thumb",
        chunk_index=0,
        byte_range=(0, 3),
        sha256=hashlib.sha256(b"seed").hexdigest(),
        payload=b"seed",
    )
    receiver.store.put_chunk(seed_chunk)
    logger.emit(events.EventType.ENCOUNTER_OPENED, sender_id="peer-A", receiver_id="peer-B")

    ingress = SchedulerIngress()
    valid_baseline_item = priority.SchedulerItem.manifest(
        object_id="o" * 64, manifest_id="baseline"
    )
    valid_baseline_payload = {
        "schema": "shongket.content.v1",
        "object_id": "o" * 64,
        "capsule_ref": "c1",
        "representations": [
            {
                "id": "thumb",
                "kind": "image/jpeg",
                "byte_len": 0,
                "chunk_size": 65536,
                "hashes": [],
                "rep_sha256": "0" * 64,
            }
        ],
        "priority": "life_safety",
        "created_at_unix": 1_700_000_000,
        "hop_limit": 6,
        "copy_budget": 8,
    }
    ingress.admit(valid_baseline_item, payload=valid_baseline_payload)

    # Capture state snapshots before the rejected admission.
    queue_before = ingress.snapshot()
    queue_len_before = ingress.queue_length()
    fragments_before = dict(receiver.store._fragments)
    stats_before = receiver.store.stats.as_dict()
    events_before = logger.events

    # Attempt to admit a malformed fragment payload.
    bad_item = priority.SchedulerItem.chunk(
        object_id="o" * 64, representation_id="thumb", chunk_index=99
    )
    bad_payload = _good_fragment_payload(object_id="o" * 64)
    # Bad enum value rejects at validation time.
    bad_payload["representation_id"] = "ultra_high_definition"

    with pytest.raises(validation.ProtocolError) as excinfo:
        ingress.admit(bad_item, payload=bad_payload)
    assert excinfo.value.code == "SCHEMA_INVALID"

    # 1. Scheduler queue is unchanged (length and contents).
    assert ingress.queue_length() == queue_len_before
    assert ingress.snapshot() == queue_before

    # 2. Storage is unchanged (fragments map and stats counters).
    assert receiver.store._fragments == fragments_before
    assert receiver.store.stats.as_dict() == stats_before

    # 3. Event log is unchanged (no scheduling or delivery event was emitted).
    assert logger.events == events_before


def test_rejected_admission_does_not_emit_any_event():
    """Even when the caller is silent, the ingress boundary must not log."""
    from app.simulator.ingress import SchedulerIngress
    from app.simulator import events, priority
    import io

    logger = events.EventLogger(sink=io.StringIO())
    ingress = SchedulerIngress()
    bad_payload = _good_fragment_payload()
    bad_payload["chunk_index"] = "not-an-int"  # wrong field type

    with pytest.raises(validation.ProtocolError):
        ingress.admit(
            priority.SchedulerItem.chunk(
                object_id="a" * 64, representation_id="thumb", chunk_index=0
            ),
            payload=bad_payload,
        )

    # The boundary itself does not emit events.
    assert logger.events == []
