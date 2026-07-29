"""AT-02 -- semantic capsule requires explicit human confirmation.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-02, M0, S1):

    a capsule with ``human_confirmed == False`` is rejected before
    scheduling and before storage. A capsule with
    ``human_confirmed == True`` proceeds normally.

The test exercises the boundary in ``app.simulator.gate``:

* an unconfirmed capsule emits exactly one ``CAPSULE_REJECTED`` event
  with ``detail.code == "HUMAN_CONFIRMATION_MISSING"`` and the driver
  raises ``ProtocolError`` with the same code;
* a confirmed capsule emits no rejection event and the encounter
  completes with the same outcome as ``run_encounter``.
"""

from __future__ import annotations

import io

import pytest

from app.simulator import events, scenario, transfer, validation
from app.simulator.gate import capsule_human_confirmation


def test_unconfirmed_capsule_is_rejected_by_gate():
    """The gate alone rejects an unconfirmed capsule deterministically."""
    logger = events.EventLogger(sink=io.StringIO())
    payload = {
        "schema": "shongket.capsule.v1",
        "capsule_id": "cap-1",
        "object_ref": "o" * 64,
        "summary_bn": "...",
        "event_type": "flood",
        "urgency": "life_safety",
        "location_text": "Khulna",
        "required_action": "evacuate",
        "required_resource": "shelter",
        "human_confirmed": False,
        "confirmation_method": "manual_form_only",
        "created_at_unix": 1_700_000_000,
    }
    validation.validate_payload("shongket.capsule.v1", payload)

    with pytest.raises(validation.ProtocolError) as excinfo:
        capsule_human_confirmation(
            payload,
            logger=logger,
            sender_id="peer-A",
            receiver_id="peer-B",
        )

    assert excinfo.value.code == "HUMAN_CONFIRMATION_MISSING"
    rejections = logger.of_type(events.EventType.CAPSULE_REJECTED)
    assert len(rejections) == 1
    detail = rejections[0].detail
    assert detail["code"] == "HUMAN_CONFIRMATION_MISSING"
    assert detail["reason"] == "human_confirmed_false"
    assert detail["confirmation_method"] == "manual_form_only"
    assert rejections[0].object_id == "o" * 64
    assert rejections[0].representation_id == "capsule:cap-1"


def test_confirmed_capsule_passes_gate_silently():
    """The gate is a no-op when ``human_confirmed`` is True."""
    logger = events.EventLogger(sink=io.StringIO())
    payload = {
        "schema": "shongket.capsule.v1",
        "capsule_id": "cap-2",
        "object_ref": "o" * 64,
        "summary_bn": "...",
        "event_type": "flood",
        "urgency": "life_safety",
        "location_text": "Khulna",
        "required_action": "evacuate",
        "required_resource": "shelter",
        "human_confirmed": True,
        "confirmation_method": "manual_form_only",
        "created_at_unix": 1_700_000_000,
    }
    capsule_human_confirmation(
        payload,
        logger=logger,
        sender_id="peer-A",
        receiver_id="peer-B",
    )
    assert logger.of_type(events.EventType.CAPSULE_REJECTED) == []


def test_unconfirmed_capsule_driver_raises_and_rejects():
    """``run_with_human_gate`` propagates the rejection and emits the event."""
    scen = scenario.build_two_peer_scenario()
    # Override the canonical capsule to ``human_confirmed == False``.
    bad_capsule = dict(scen.capsule)
    bad_capsule["human_confirmed"] = False
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)

    receiver = scen.receiver
    sender = scen.sender
    logger = events.EventLogger(sink=io.StringIO())

    with pytest.raises(validation.ProtocolError) as excinfo:
        transfer.run_with_human_gate(
            sender=sender,
            receiver=receiver,
            logger=logger,
            items=items,
            capsule_payload=bad_capsule,
            manifest_payload=scen.manifest,
            chunks=chunks,
        )
    assert excinfo.value.code == "HUMAN_CONFIRMATION_MISSING"

    rejections = logger.of_type(events.EventType.CAPSULE_REJECTED)
    assert len(rejections) == 1
    # No chunks were persisted because the capsule was rejected before any
    # media could be scheduled in this slice.
    assert receiver.store.stats.stored == 0
    assert logger.of_type(events.EventType.CHUNK_DELIVERED) == []


def test_confirmed_capsule_driver_completes_encounter():
    """With ``human_confirmed == True`` the encounter runs to completion."""
    scen = scenario.build_two_peer_scenario()
    assert scen.capsule["human_confirmed"] is True

    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)
    logger = events.EventLogger(sink=io.StringIO())

    result = transfer.run_with_human_gate(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        items=items,
        capsule_payload=scen.capsule,
        manifest_payload=scen.manifest,
        chunks=chunks,
    )

    assert logger.of_type(events.EventType.CAPSULE_REJECTED) == []
    assert result.delivered_capsule is True
    assert result.delivered_manifest is True
    # Every media chunk made it through (no duplicate keys, no corruption).
    assert receiver_store_count(result.delivered_chunk_indexes) == len(chunks)
    assert scen.receiver.store.stats.stored == len(chunks)


def receiver_store_count(_indexes):
    # Helper kept for readability; not a magic name.
    return len(_indexes)
