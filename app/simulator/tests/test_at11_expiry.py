"""AT-11 -- expired content is not forwarded.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-11, M0, S1):

    with TTL exceeded, an attempt to forward is refused and the object
    is not scheduled.

Evidence required: refusal log showing the object not scheduled past
``expires_at``.

Expiry is evaluated against a deterministic simulator tick supplied by
the caller (``now_unix``). Nothing here reads ``time.time()`` or
``datetime.now()``; the module imports no time source at all.

Boundary: expiry is inclusive, so ``now_unix == expires_at_unix`` is
already expired. PROTOCOL_SPEC.md §7 models this as
``Persisted --> Expiring: expires_at reached``, and §6.0 admits an object
for forwarding only when it is "not expired".
"""

from __future__ import annotations

import io

from app.simulator import events, manifest, priority, scenario, transfer


CREATED_AT = 1_700_000_000
EXPIRES_AT = 1_700_000_600


def _expiring_manifest(scen, *, expires_at_unix: int | None = EXPIRES_AT) -> dict:
    """Rebuild the scenario manifest with an explicit expiry stamp."""
    return manifest.build_manifest(
        object_id=scen.object_id,
        capsule_id=scen.capsule["capsule_id"],
        representations=scen.manifest["representations"],
        priority="life_safety",
        expires_at_unix=expires_at_unix,
        created_at_unix=CREATED_AT,
    )


def _forward_at(scen, now_unix: int, *, expires_at_unix: int | None = EXPIRES_AT):
    items = scenario.schedule_full_transfer(scen)
    chunks = scenario.all_chunks(scen)
    logger = events.EventLogger(sink=io.StringIO())
    result = transfer.run_forwarding_encounter(
        sender=scen.sender,
        receiver=scen.receiver,
        logger=logger,
        items=items,
        manifest_payload=_expiring_manifest(scen, expires_at_unix=expires_at_unix),
        chunks=chunks,
        now_unix=now_unix,
    )
    return logger, result, chunks


# --- the expiry predicate itself --------------------------------------------


def test_is_expired_boundary_conditions():
    before = priority.is_expired(expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT - 1)
    at = priority.is_expired(expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT)
    after = priority.is_expired(expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT + 1)

    assert before is False
    assert at is True
    assert after is True

    # A null expiry never expires, at any tick.
    assert priority.is_expired(expires_at_unix=None, now_unix=EXPIRES_AT + 10_000) is False


def test_expired_object_never_enters_the_forwarding_queue():
    """The queue is the scheduling boundary: expired content yields none."""
    scen = scenario.build_two_peer_scenario()
    items = scenario.schedule_full_transfer(scen)
    assert items, "fixture must produce a non-empty queue when unexpired"

    admitted_before = priority.admit_for_forwarding(
        items, expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT - 1
    )
    admitted_at = priority.admit_for_forwarding(
        items, expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT
    )
    admitted_after = priority.admit_for_forwarding(
        items, expires_at_unix=EXPIRES_AT, now_unix=EXPIRES_AT + 1
    )

    assert len(admitted_before) == len(items)
    assert admitted_at == []
    assert admitted_after == []


# --- tick < expiry ----------------------------------------------------------


def test_before_expiry_content_is_forwarded():
    scen = scenario.build_two_peer_scenario()
    logger, result, chunks = _forward_at(scen, EXPIRES_AT - 1)

    assert result.admitted is True
    assert result.refusal_reason is None
    assert result.queued_items > 0
    assert result.delivered_chunk_indexes

    # Content actually reached the receiver.
    assert scen.receiver.store.stats.stored == len(chunks)
    assert logger.of_type(events.EventType.CHUNK_DELIVERED)

    queued = logger.of_type(events.EventType.FORWARD_QUEUED)
    assert len(queued) == 1
    assert queued[0].detail["now_unix"] == EXPIRES_AT - 1
    assert queued[0].detail["expires_at_unix"] == EXPIRES_AT
    assert logger.of_type(events.EventType.FORWARD_REFUSED) == []


def test_null_expiry_is_forwarded():
    """An object with no expiry stamp forwards normally."""
    scen = scenario.build_two_peer_scenario()
    _logger, result, chunks = _forward_at(
        scen, CREATED_AT + 10_000_000, expires_at_unix=None
    )
    assert result.admitted is True
    assert scen.receiver.store.stats.stored == len(chunks)


# --- tick == expiry and tick > expiry ---------------------------------------


def _assert_refused(scen, logger, result, now_unix: int) -> None:
    assert result.admitted is False
    assert result.refusal_reason == "EXPIRED"
    assert result.queued_items == 0
    assert result.delivered_chunk_indexes == []

    # Nothing was transmitted.
    assert logger.of_type(events.EventType.CHUNK_DELIVERED) == []
    assert logger.of_type(events.EventType.FORWARD_QUEUED) == []
    # The encounter was never even opened.
    assert logger.of_type(events.EventType.ENCOUNTER_OPENED) == []

    # Receiver storage is untouched.
    assert scen.receiver.store.stats.stored == 0
    assert scen.receiver.store.snapshot_fragments() == {}

    # Deterministic refusal evidence.
    refused = logger.of_type(events.EventType.FORWARD_REFUSED)
    assert len(refused) == 1
    detail = refused[0].detail
    assert detail["reason"] == "EXPIRED"
    assert detail["ack_status"] == "expired"
    assert detail["now_unix"] == now_unix
    assert detail["expires_at_unix"] == EXPIRES_AT
    assert detail["queued_items"] == 0
    assert refused[0].object_id == scen.object_id


def test_at_expiry_forwarding_is_refused():
    scen = scenario.build_two_peer_scenario()
    logger, result, _chunks = _forward_at(scen, EXPIRES_AT)
    _assert_refused(scen, logger, result, EXPIRES_AT)


def test_after_expiry_forwarding_is_refused():
    scen = scenario.build_two_peer_scenario()
    logger, result, _chunks = _forward_at(scen, EXPIRES_AT + 1)
    _assert_refused(scen, logger, result, EXPIRES_AT + 1)


# --- locally stored expired content -----------------------------------------


def test_expired_content_already_stored_is_retained_but_not_forwarded():
    """Expiry blocks forwarding; it does not delete local content.

    No canonical M0 document requires deletion, so the receiver keeps
    what it already verified.
    """
    scen = scenario.build_two_peer_scenario()
    chunks = scenario.all_chunks(scen)

    # The receiver already holds some verified content.
    held = chunks[:2]
    for chunk in held:
        scen.receiver.store.restore_fragment(chunk)
    before = scen.receiver.store.snapshot_fragments()
    assert len(before) == len(held)

    logger, result, _chunks = _forward_at(scen, EXPIRES_AT + 500)

    assert result.admitted is False
    assert result.refusal_reason == "EXPIRED"
    # Previously stored content survives the refusal, unchanged.
    assert scen.receiver.store.snapshot_fragments() == before
    assert logger.of_type(events.EventType.CHUNK_DELIVERED) == []


def test_expiry_decision_is_deterministic_across_runs():
    """Same tick in, byte-identical refusal log out."""
    logs = []
    for _ in range(2):
        scen = scenario.build_two_peer_scenario()
        items = scenario.schedule_full_transfer(scen)
        sink = io.StringIO()
        logger = events.EventLogger(sink=sink)
        transfer.run_forwarding_encounter(
            sender=scen.sender,
            receiver=scen.receiver,
            logger=logger,
            items=items,
            manifest_payload=_expiring_manifest(scen),
            chunks=scenario.all_chunks(scen),
            now_unix=EXPIRES_AT + 7,
        )
        logs.append(sink.getvalue())
    assert logs[0] == logs[1]
