"""AT-17 -- oversized-payload rejection.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-17, M0, S1):

    with an oversized payload, sending is rejected with a
    ``ProtocolError``.

Evidence required: rejection log.

Canonical limits, quoted from PROTOCOL_SPEC.md. There are four, and they
apply to different protocol objects:

===========================  ==========  ==============================
Object                       Limit       Source
===========================  ==========  ==============================
SemanticCapsule              4096 B      §3.1 "capsule <= 4 KB serialized"
ContentManifest              32768 B     §3.2 "manifest <= 32 KB serialized"
FragmentDescriptor           512 B       §3.4 "<= 512 B serialized"
Transport frame              1048576 B   §3.5 ``max_payload``; §6.0 factor 10
===========================  ==========  ==============================

All four bound the *serialized* form. The 512 B fragment limit bounds the
**descriptor**, never the chunk payload it describes -- a 64 KB chunk
carries a ~250 B descriptor. Chunk payload bytes are bounded by the
transport frame limit instead, which is why ordinary chunk transfer is
unaffected by any of this.

The canonical error code is ``PAYLOAD_TOO_LARGE`` from the
``shongket.error.v1`` enum (§3.8). PROTOCOL_SPEC.md §8 requires oversized
payloads to be "rejected at framing layer" with "size limits enforced
before parse", so the size check runs ahead of every schema check. AT-20
is explicitly scoped to payloads "within the size limit", so the two
boundaries are disjoint.

Fixtures are padded to the exact limit rather than being made
arbitrarily huge: the largest byte string this module builds is
1048577 B, one byte over the frame limit.
"""

from __future__ import annotations

import io

import pytest

from app.simulator import (
    capsule,
    events,
    gate,
    ingress,
    manifest,
    priority,
    scenario,
    transfer,
    validation,
)
from app.simulator.chunks import Chunk
from app.simulator.hashutil import sha256_hex
from app.simulator.peer import SimulatedPeer


CAPSULE_LIMIT = 4 * 1024
MANIFEST_LIMIT = 32 * 1024
FRAGMENT_LIMIT = 512
FRAME_LIMIT = 1_048_576


def _logger():
    return events.EventLogger(sink=io.StringIO())


def _size(payload: dict) -> int:
    return len(validation.canonical_bytes(payload))


def _pad_field_to(payload: dict, key: str, target: int) -> dict:
    """Pad a top-level ASCII string field so the payload is exactly ``target``.

    Each ASCII character added to a JSON string adds exactly one byte to
    the canonical encoding, so the padding length is the size deficit.
    """
    payload = dict(payload)
    payload[key] = ""
    deficit = target - _size(payload)
    assert deficit >= 0, f"payload already exceeds {target} bytes"
    payload[key] = "a" * deficit
    assert _size(payload) == target
    return payload


# --- the limits are the canonical ones --------------------------------------


def test_canonical_size_limits_match_the_specification():
    assert validation.size_limit_for("shongket.capsule.v1") == CAPSULE_LIMIT
    assert validation.size_limit_for("shongket.content.v1") == MANIFEST_LIMIT
    assert validation.size_limit_for("shongket.fragment.v1") == FRAGMENT_LIMIT
    assert validation.MAX_FRAME_BYTES == FRAME_LIMIT


# --- capsule boundary (4096 B) ----------------------------------------------


def _base_capsule() -> dict:
    scen = scenario.build_two_peer_scenario()
    return capsule.build_capsule(
        object_id=scen.object_id,
        summary_bn="Jol bere jacche.",
        created_at_unix=1_700_000_000,
    )


def test_capsule_exactly_at_limit_is_accepted():
    payload = _pad_field_to(_base_capsule(), "location_text", CAPSULE_LIMIT)
    assert _size(payload) == CAPSULE_LIMIT
    validation.validate_payload("shongket.capsule.v1", payload)  # no raise


def test_capsule_one_byte_over_limit_is_rejected():
    payload = _pad_field_to(_base_capsule(), "location_text", CAPSULE_LIMIT + 1)
    assert _size(payload) == CAPSULE_LIMIT + 1

    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.capsule.v1", payload)
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"


# --- manifest boundary (32768 B) --------------------------------------------


def _base_manifest() -> dict:
    scen = scenario.build_two_peer_scenario()
    return manifest.build_manifest(
        object_id=scen.object_id,
        capsule_id=scen.capsule["capsule_id"],
        representations=scen.manifest["representations"],
        priority="life_safety",
        created_at_unix=1_700_000_000,
    )


def test_manifest_exactly_at_limit_is_accepted():
    payload = _pad_field_to(_base_manifest(), "capsule_ref", MANIFEST_LIMIT)
    validation.validate_payload("shongket.content.v1", payload)


def test_manifest_one_byte_over_limit_is_rejected():
    payload = _pad_field_to(_base_manifest(), "capsule_ref", MANIFEST_LIMIT + 1)
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.content.v1", payload)
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"


# --- fragment-descriptor boundary (512 B) -----------------------------------


def _base_descriptor() -> dict:
    return {
        "schema": "shongket.fragment.v1",
        "object_id": "b" * 64,
        "representation_id": "original",
        "chunk_index": 3,
        "chunk_size": 65536,
        "byte_range": [196608, 262143],
        "hash": "c" * 64,
    }


def test_fragment_descriptor_exactly_at_limit_is_accepted():
    payload = _pad_field_to(_base_descriptor(), "object_id", FRAGMENT_LIMIT)
    validation.validate_payload("shongket.fragment.v1", payload)


def test_fragment_descriptor_one_byte_over_limit_is_rejected():
    payload = _pad_field_to(_base_descriptor(), "object_id", FRAGMENT_LIMIT + 1)
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.validate_payload("shongket.fragment.v1", payload)
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"


# --- transport-frame boundary (1048576 B) -----------------------------------


def test_frame_exactly_at_max_payload_is_accepted():
    validation.check_frame_size(b"\x00" * FRAME_LIMIT)  # no raise


def test_frame_one_byte_over_max_payload_is_rejected():
    with pytest.raises(validation.ProtocolError) as excinfo:
        validation.check_frame_size(b"\x00" * (FRAME_LIMIT + 1))
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"


def test_oversized_frame_is_refused_before_transmission_or_storage():
    sender = SimulatedPeer(peer_id="peer-A")
    receiver = SimulatedPeer(peer_id="peer-B")
    logger = _logger()
    payload = b"\xab" * (FRAME_LIMIT + 1)
    oversized = Chunk(
        object_id="d" * 64,
        representation_id="original",
        chunk_index=0,
        byte_range=(0, len(payload) - 1),
        sha256=sha256_hex(payload),
        payload=payload,
    )
    result = transfer.EncounterResult(sender_id="peer-A", receiver_id="peer-B")

    sent = transfer._send_chunk(
        sender=sender, receiver=receiver, chunk=oversized, logger=logger, result=result
    )

    assert sent is False
    # Nothing transmitted, nothing stored.
    assert sender.has_outgoing() is False
    assert receiver.has_incoming() is False
    assert receiver.store.stats.stored == 0
    assert receiver.store.used_bytes == 0
    # Only the canonical rejection evidence was emitted.
    rejected = logger.of_type(events.EventType.PAYLOAD_REJECTED)
    assert len(rejected) == 1
    detail = rejected[0].detail
    assert detail["code"] == "PAYLOAD_TOO_LARGE"
    assert detail["kind"] == "frame"
    assert detail["encoded_bytes"] == FRAME_LIMIT + 1
    assert detail["limit_bytes"] == FRAME_LIMIT
    assert logger.of_type(events.EventType.CHUNK_DELIVERED) == []


# --- rejection happens before scheduling and persistence --------------------


def test_oversized_payload_does_not_enter_the_scheduler_queue():
    scen = scenario.build_two_peer_scenario()
    queue = ingress.SchedulerIngress()
    payload = _pad_field_to(_base_capsule(), "location_text", CAPSULE_LIMIT + 1)
    item = priority.SchedulerItem.capsule(
        object_id=scen.object_id, capsule_id="x" * 64, urgency="life_safety"
    )
    queue_before = queue.snapshot()

    with pytest.raises(validation.ProtocolError) as excinfo:
        queue.admit(item, payload=payload)
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"

    assert queue.queue_length() == 0
    assert queue.snapshot() == queue_before


def test_oversized_descriptor_leaves_existing_stored_data_intact():
    scen = scenario.build_two_peer_scenario(chunk_size=16_384)
    receiver = SimulatedPeer(peer_id="peer-B")
    good = scen.plans["original"].chunks[0]
    receiver.store.put_chunk(good)

    fragments_before = receiver.store.snapshot_fragments()
    used_before = receiver.store.used_bytes

    # An object_id long enough to push the descriptor past 512 B.
    oversized_descriptor_chunk = Chunk(
        object_id="e" * 600,
        representation_id="original",
        chunk_index=1,
        byte_range=(0, 15),
        sha256=sha256_hex(b"z" * 16),
        payload=b"z" * 16,
    )

    with pytest.raises(validation.ProtocolError) as excinfo:
        receiver.store.put_chunk(oversized_descriptor_chunk)
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"

    assert receiver.store.snapshot_fragments() == fragments_before
    assert receiver.store.used_bytes == used_before
    assert receiver.store.stats.rejected_oversize == 1
    assert receiver.store.stats.rejected_schema == 0
    assert receiver.store.stats.stored == 1


def test_size_gate_emits_rejection_evidence():
    logger = _logger()
    payload = _pad_field_to(_base_capsule(), "location_text", CAPSULE_LIMIT + 1)

    with pytest.raises(validation.ProtocolError) as excinfo:
        gate.payload_size_gate(
            "shongket.capsule.v1",
            payload,
            logger=logger,
            sender_id="peer-A",
            receiver_id="peer-B",
        )
    assert excinfo.value.code == "PAYLOAD_TOO_LARGE"

    rejected = logger.of_type(events.EventType.PAYLOAD_REJECTED)
    assert len(rejected) == 1
    detail = rejected[0].detail
    assert detail["reason"] == "payload_too_large"
    assert detail["code"] == "PAYLOAD_TOO_LARGE"
    assert detail["kind"] == "shongket.capsule.v1"
    assert detail["encoded_bytes"] == CAPSULE_LIMIT + 1
    assert detail["limit_bytes"] == CAPSULE_LIMIT


def test_size_gate_passes_schema_failures_through_untouched():
    """AT-20's boundary keeps its own code and emits no size evidence."""
    logger = _logger()
    payload = dict(_base_capsule())
    del payload["capsule_id"]

    with pytest.raises(validation.ProtocolError) as excinfo:
        gate.payload_size_gate(
            "shongket.capsule.v1",
            payload,
            logger=logger,
            sender_id="peer-A",
            receiver_id="peer-B",
        )
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert logger.of_type(events.EventType.PAYLOAD_REJECTED) == []


# --- declared size versus actual encoded size -------------------------------


def test_declared_chunk_size_disagreeing_with_actual_payload_is_rejected():
    """A descriptor may not under-declare the bytes it carries.

    PROTOCOL_SPEC.md §3.4 requires the hash to equal SHA-256 of the
    actual bytes, so a mismatched declaration is caught by the integrity
    check even when the descriptor itself is within its size limit.
    """
    receiver = SimulatedPeer(peer_id="peer-B")
    actual = b"y" * 4096
    lying = Chunk(
        object_id="f" * 64,
        representation_id="original",
        chunk_index=0,
        byte_range=(0, 15),  # claims 16 bytes
        sha256=sha256_hex(b"y" * 16),  # hash of the claimed, not actual, bytes
        payload=actual,
    )

    with pytest.raises(validation.ProtocolError) as excinfo:
        receiver.store.put_chunk(lying)
    assert excinfo.value.code == "SCHEMA_INVALID"
    assert receiver.store.stats.stored == 0
    assert receiver.store.used_bytes == 0


# --- the boundary does not disturb ordinary transfer ------------------------


def test_ordinary_chunk_transfer_is_unaffected():
    """Normal 64 KB chunks are far below every limit and still flow."""
    scen = scenario.build_two_peer_scenario()
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)
    logger = _logger()

    result = transfer.run_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        items=items,
        capsule_payload=scen.capsule,
        manifest_payload=scen.manifest,
        chunks=chunks,
    )

    assert len(result.delivered_chunk_indexes) == len(chunks)
    assert scen.receiver.store.stats.stored == len(chunks)
    assert scen.receiver.store.stats.rejected_oversize == 0
    assert logger.of_type(events.EventType.PAYLOAD_REJECTED) == []
    # Every real descriptor is comfortably inside the 512 B limit.
    for chunk in chunks:
        descriptor = scen.receiver.store._descriptor(chunk)
        assert _size(descriptor) <= FRAGMENT_LIMIT


def test_storage_budget_path_still_works_under_the_size_boundary():
    """AT-12 accounting is unchanged by the AT-17 checks."""
    scen = scenario.build_two_peer_scenario(chunk_size=16_384)
    chunks = scen.plans["original"].chunks[:3]
    receiver = SimulatedPeer(peer_id="peer-B")
    receiver.store.capacity_bytes = sum(len(c.payload) for c in chunks)

    for chunk in chunks:
        receiver.store.put_chunk(chunk)

    assert receiver.store.stats.stored == 3
    assert receiver.store.remaining_bytes == 0
    assert receiver.store.stats.rejected_oversize == 0
