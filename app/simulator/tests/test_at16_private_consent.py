"""AT-16 -- private-content consent boundary.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-16, M0, S1):

    with a private marker, forwarding is refused unless there is
    explicit consent.

Evidence required: refusal log.

Canonical basis: PROTOCOL_SPEC.md §8 ("Private content forwarding |
explicit consent required"), RISK_REGISTER.md R-11 ("explicit consent
gate per object class") and AGENTS.md ("require user confirmation before
publicly forwarding private content").

Canonical gap. No schema in PROTOCOL_SPEC.md §3 declares the field names
that carry the private marker and the consent decision, and
PRODUCT_DECISIONS.md still lists "private versus public content
encryption" as an open question. ``gate.FIELD_PRIVATE`` and
``gate.FIELD_FORWARDING_CONSENT`` are the minimal encoding of the stated
rule; the *behaviour* asserted here is canonical even though the field
names await M1 schema-freezing.

No encryption, authentication, identity infrastructure or key management
is introduced -- consent is a recorded decision, nothing more.
"""

from __future__ import annotations

import io

import pytest

from app.simulator import events, gate, manifest, scenario, transfer, validation


CREATED_AT = 1_700_000_000


def _manifest(scen, *, private=None, consent="__absent__") -> dict:
    """Rebuild the scenario manifest with privacy fields applied."""
    payload = manifest.build_manifest(
        object_id=scen.object_id,
        capsule_id=scen.capsule["capsule_id"],
        representations=scen.manifest["representations"],
        priority="life_safety",
        created_at_unix=CREATED_AT,
    )
    if private is not None:
        payload[gate.FIELD_PRIVATE] = private
    if consent != "__absent__":
        payload[gate.FIELD_FORWARDING_CONSENT] = consent
    return payload


def _forward(scen, manifest_payload):
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)
    logger = events.EventLogger(sink=io.StringIO())
    result = transfer.run_forwarding_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        items=items,
        manifest_payload=manifest_payload,
        chunks=chunks,
        now_unix=CREATED_AT,
    )
    return logger, result, chunks


# --- refusal boundaries ------------------------------------------------------


@pytest.mark.parametrize(
    "consent, expected_reason",
    [
        ("__absent__", "consent_missing"),
        (False, "consent_false"),
        ("yes", "consent_malformed"),
        (1, "consent_malformed"),
        (None, "consent_missing"),
    ],
)
def test_private_content_without_explicit_consent_is_refused(
    consent, expected_reason
):
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=True, consent=consent)
    logger = events.EventLogger(sink=io.StringIO())

    with pytest.raises(validation.ProtocolError) as excinfo:
        gate.private_content_consent(
            payload, logger=logger, sender_id="peer-A", receiver_id="peer-B"
        )

    assert excinfo.value.code == "CONSENT_REQUIRED"
    assert excinfo.value.object_id == scen.object_id

    refusals = logger.of_type(events.EventType.CONSENT_REJECTED)
    assert len(refusals) == 1
    detail = refusals[0].detail
    assert detail["reason"] == expected_reason
    assert detail["code"] == "CONSENT_REQUIRED"
    assert detail["private"] is True
    assert refusals[0].object_id == scen.object_id


def test_refusal_leaves_queue_storage_and_events_unchanged():
    """The gate runs before scheduling, transmission and persistence."""
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=True)

    fragments_before = scen.receiver.store.snapshot_fragments()
    stats_before = scen.receiver.store.stats.as_dict()

    with pytest.raises(validation.ProtocolError) as excinfo:
        _forward(scen, payload)
    assert excinfo.value.code == "CONSENT_REQUIRED"

    # Receiver storage untouched.
    assert scen.receiver.store.snapshot_fragments() == fragments_before
    assert scen.receiver.store.stats.as_dict() == stats_before
    assert scen.receiver.store.stats.stored == 0
    # Sender transmission state untouched: nothing was ever queued out.
    assert scen.sender.has_outgoing() is False
    assert scen.receiver.has_incoming() is False


def test_refusal_emits_no_delivery_events_and_opens_no_encounter():
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=True, consent=False)
    items = scenario.schedule_full_transfer(scen)
    logger = events.EventLogger(sink=io.StringIO())

    with pytest.raises(validation.ProtocolError):
        transfer.run_forwarding_encounter(
            sender=scen.sender,
            receiver=scen.receiver,
            logger=logger,
            items=items,
            manifest_payload=payload,
            chunks=scenario.all_chunks(scen),
            now_unix=CREATED_AT,
        )

    assert logger.of_type(events.EventType.CHUNK_DELIVERED) == []
    assert logger.of_type(events.EventType.FORWARD_QUEUED) == []
    assert logger.of_type(events.EventType.ENCOUNTER_OPENED) == []
    # The only event emitted is the canonical refusal.
    assert [ev.type for ev in logger.events] == [events.EventType.CONSENT_REJECTED]


# --- permitted paths ---------------------------------------------------------


def test_private_content_with_explicit_consent_is_forwarded():
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=True, consent=True)

    logger, result, chunks = _forward(scen, payload)

    assert result.admitted is True
    assert result.refusal_reason is None
    assert scen.receiver.store.stats.stored == len(chunks)
    assert logger.of_type(events.EventType.CONSENT_REJECTED) == []
    assert logger.of_type(events.EventType.FORWARD_QUEUED)


def test_public_content_is_not_blocked_by_the_private_gate():
    """Ordinary public content must pass the gate untouched."""
    scen = scenario.build_two_peer_scenario()
    # No private marker at all -- the default shape produced elsewhere.
    payload = _manifest(scen)
    assert gate.FIELD_PRIVATE not in payload

    logger, result, chunks = _forward(scen, payload)

    assert result.admitted is True
    assert scen.receiver.store.stats.stored == len(chunks)
    assert logger.of_type(events.EventType.CONSENT_REJECTED) == []


def test_explicitly_public_content_is_not_blocked():
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=False)
    logger = events.EventLogger(sink=io.StringIO())

    # Returns without raising, and emits nothing.
    gate.private_content_consent(
        payload, logger=logger, sender_id="peer-A", receiver_id="peer-B"
    )
    assert logger.events == []


def test_public_content_ignores_a_stray_consent_field():
    """Consent is only consulted for private objects."""
    scen = scenario.build_two_peer_scenario()
    payload = _manifest(scen, private=False, consent=False)
    logger = events.EventLogger(sink=io.StringIO())

    gate.private_content_consent(
        payload, logger=logger, sender_id="peer-A", receiver_id="peer-B"
    )
    assert logger.events == []


def test_is_private_defaults_to_public():
    assert gate.is_private({}) is False
    assert gate.is_private({gate.FIELD_PRIVATE: False}) is False
    assert gate.is_private({gate.FIELD_PRIVATE: True}) is True
    # A non-boolean marker is not a private marker.
    assert gate.is_private({gate.FIELD_PRIVATE: "true"}) is False


def test_consent_refusal_is_deterministic():
    logs = []
    for _ in range(2):
        scen = scenario.build_two_peer_scenario()
        payload = _manifest(scen, private=True)
        sink = io.StringIO()
        logger = events.EventLogger(sink=sink)
        with pytest.raises(validation.ProtocolError):
            gate.private_content_consent(
                payload, logger=logger, sender_id="peer-A", receiver_id="peer-B"
            )
        logs.append(sink.getvalue())
    assert logs[0] == logs[1]
