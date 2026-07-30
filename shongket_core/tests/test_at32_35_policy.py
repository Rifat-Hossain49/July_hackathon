"""AT-32, AT-33, AT-34, AT-35 -- error model, privacy and forwarding policy.

Canonical definitions (ACCEPTANCE_TESTS.md):

* **AT-32** every raised code exists in the canonical enum; every enum
  member is either reached by a test or explicitly recorded as
  unreachable-by-design with a reason; each code carries exactly one
  terminal/retryable classification.
* **AT-33** a terminal failure re-offered with identical input fails
  identically with no state change; a retryable failure succeeds once
  the blocking condition clears; neither mutates state on a failing
  attempt.
* **AT-34** legacy `private` migrates to `visibility`; malformed
  `visibility` is `SCHEMA_INVALID`; non-boolean `forwarding_consent` is
  `CONSENT_REQUIRED`; every AT-16 assertion still holds after migration.
* **AT-35** a private object *with valid consent* aimed at a
  `public_only` peer is refused with `PEER_REFUSES_PRIVATE` before
  queueing and transmission; ordinary peers and public objects are
  permitted. Consent does not override `public_only`.

Runtime boundary: `core/errors`, `core/store`, `core/policy`,
`core/migrate`.
"""

from __future__ import annotations

import copy

import pytest

from shongket_core import ErrorClass, ErrorCode, ProtocolError, codec
from shongket_core.errors import ERROR_CLASSES
from shongket_core.evidence import EvidenceLog, EventCode
from shongket_core.migrate import migrate_privacy_fields
from shongket_core.policy import (
    PeerCapability,
    advance_forwarding_state,
    evaluate_forwarding,
    has_consent,
    identity_is_stable,
    read_visibility,
)
from shongket_core.store import Fragment, FragmentStore


NOW = 1_700_000_000
ORDINARY = PeerCapability(peer_id="peer-B", public_only=False)
PUBLIC_ONLY = PeerCapability(peer_id="peer-P", public_only=True)


def manifest(**overrides) -> dict:
    base = {
        "schema": "shongket.content.v1.0",
        "object_id": "a" * 64,
        "capsule_ref": "c" * 64,
        "representations": [],
        "priority": "life_safety",
        "created_at_unix": NOW - 100,
        "hop_limit": 6,
        "copy_budget": 8,
    }
    base.update(overrides)
    return base


def frag(index: int) -> Fragment:
    payload = bytes([80 + index]) * 16
    return Fragment(
        object_id="a" * 64,
        representation_id="original",
        chunk_index=index,
        byte_range=(index * 16, index * 16 + 15),
        sha256=codec.sha256_hex(payload),
        payload=payload,
    )


# --- AT-32 canonical error taxonomy -------------------------------------------

#: Enum members not reachable from the M1 core, each with a stated reason.
UNREACHABLE_BY_DESIGN = {
    ErrorCode.SIGNATURE_INVALID: "signature verification is not implemented in M1; "
                                 "Ed25519 signing is later-milestone work",
    ErrorCode.UNKNOWN_OBJECT: "raised by the transfer negotiation layer, which is "
                              "M2 two-process work, not the M1 core",
    ErrorCode.INTERNAL: "reserved for defects; must never be produced by valid input",
}


def test_every_enum_member_is_classified_exactly_once():
    assert set(ERROR_CLASSES) == set(ErrorCode)
    for code, klass in ERROR_CLASSES.items():
        assert isinstance(klass, ErrorClass)
        assert klass in (ErrorClass.TERMINAL, ErrorClass.RETRYABLE)


def test_every_enum_member_is_reached_or_explicitly_excused():
    reached = set(REACHED_CODES)
    excused = set(UNREACHABLE_BY_DESIGN)
    assert reached.isdisjoint(excused), "a code cannot be both reached and excused"
    assert reached | excused == set(ErrorCode)
    for code, reason in UNREACHABLE_BY_DESIGN.items():
        assert isinstance(reason, str) and len(reason) > 20


def test_undocumented_codes_cannot_be_raised():
    with pytest.raises(TypeError, match="undocumented error codes"):
        ProtocolError("NOT_A_REAL_CODE", "nope")  # type: ignore[arg-type]


def test_error_details_are_deterministic_and_address_free():
    import re

    address = re.compile(r"0x[0-9a-fa-f]{6,}")
    details = []
    for _ in range(3):
        try:
            read_visibility(manifest(visibility="sideways"))
        except ProtocolError as exc:
            details.append(exc.detail)
    assert len(set(details)) == 1
    assert not address.search(details[0])
    # Collections rendered in sorted order, not set order.
    assert "['private', 'public']" in details[0]


def test_error_dict_is_canonical_and_serializable():
    try:
        read_visibility(manifest(visibility=5))
    except ProtocolError as exc:
        payload = exc.to_dict()
    assert payload["schema"] == "shongket.error.v1"
    assert payload["code"] == "SCHEMA_INVALID"
    codec.canonical_bytes(payload)


# --- AT-33 terminal versus retryable -------------------------------------------


def test_terminal_failure_repeats_identically_with_no_state_change():
    store = FragmentStore(capacity_bytes=1_000)
    store.put(frag(0))
    before = store.inventory()
    before_bytes = store.used_bytes

    bad = Fragment(
        object_id="a" * 64,
        representation_id="original",
        chunk_index=9,
        byte_range=(0, 15),
        sha256=codec.sha256_hex(b"expected"),
        payload=b"actual-payload!!",
    )

    codes, details = set(), set()
    for _ in range(3):
        with pytest.raises(ProtocolError) as excinfo:
            store.put(bad)
        codes.add(excinfo.value.code)
        details.add(excinfo.value.detail)
        assert excinfo.value.error_class is ErrorClass.TERMINAL

    assert codes == {ErrorCode.SCHEMA_INVALID}
    assert len(details) == 1
    assert store.inventory() == before
    assert store.used_bytes == before_bytes


def test_retryable_failure_succeeds_once_the_condition_clears():
    store = FragmentStore(capacity_bytes=16)
    store.put(frag(0))
    before = store.inventory()

    with pytest.raises(ProtocolError) as excinfo:
        store.put(frag(1))
    assert excinfo.value.code is ErrorCode.OUT_OF_BUDGET
    assert excinfo.value.retryable is True
    assert store.inventory() == before, "no mutation on the failing attempt"

    # Clear the blocking condition: free capacity.
    store.capacity_bytes = 64
    assert store.put(frag(1)) is True
    assert store.used_bytes == store.recompute_used_bytes()


def test_repeated_policy_refusal_is_deterministic_and_side_effect_free():
    payload = manifest(visibility="private")
    snapshot = copy.deepcopy(payload)
    outcomes = []
    for _ in range(3):
        decision = evaluate_forwarding(payload, now_unix=NOW, peer=ORDINARY)
        outcomes.append((decision.admitted, decision.code, decision.clause))
    assert len(set(outcomes)) == 1
    assert payload == snapshot, "manifest unmutated by a refusal"


# --- AT-34 privacy and consent compatibility -----------------------------------


@pytest.mark.parametrize(
    "legacy, expected",
    [({"private": True}, "private"), ({"private": False}, "public"), ({}, "public")],
)
def test_legacy_private_migrates_to_visibility(legacy, expected):
    migrated = migrate_privacy_fields(manifest(**legacy))
    assert migrated["visibility"] == expected
    assert "private" not in migrated
    assert read_visibility(migrated) == expected


@pytest.mark.parametrize("value", ["Private", "PUBLIC", "", "unknown", 1, True, None, []])
def test_malformed_visibility_is_schema_invalid(value):
    with pytest.raises(ProtocolError) as excinfo:
        read_visibility(manifest(visibility=value))
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


@pytest.mark.parametrize("value", ["yes", "true", 1, 0, [], {}])
def test_non_boolean_consent_is_consent_required(value):
    decision = evaluate_forwarding(
        manifest(visibility="private", forwarding_consent=value),
        now_unix=NOW,
        peer=ORDINARY,
    )
    assert decision.admitted is False
    assert decision.code == ErrorCode.CONSENT_REQUIRED.value
    assert decision.detail["reason"] == "consent_malformed"


def test_at16_refusal_matrix_still_holds_after_migration():
    """The M0 AT-16 matrix, re-run through the M1 policy."""
    cases = [
        ({}, "consent_missing"),
        ({"forwarding_consent": False}, "consent_false"),
        ({"forwarding_consent": "yes"}, "consent_malformed"),
        ({"forwarding_consent": 1}, "consent_malformed"),
    ]
    for extra, reason in cases:
        migrated = migrate_privacy_fields(manifest(private=True, **extra))
        decision = evaluate_forwarding(migrated, now_unix=NOW, peer=ORDINARY)
        assert decision.admitted is False
        assert decision.code == ErrorCode.CONSENT_REQUIRED.value
        assert decision.detail["reason"] == reason

    consented = migrate_privacy_fields(manifest(private=True, forwarding_consent=True))
    assert evaluate_forwarding(consented, now_unix=NOW, peer=ORDINARY).admitted is True


def test_public_content_needs_no_consent():
    for extra in ({}, {"visibility": "public"}, {"visibility": "public", "forwarding_consent": False}):
        assert evaluate_forwarding(manifest(**extra), now_unix=NOW, peer=ORDINARY).admitted


def test_only_literal_true_grants_consent():
    assert has_consent({"forwarding_consent": True}) is True
    for value in (1, "true", "yes", [1], {"a": 1}, None, False, 0):
        assert has_consent({"forwarding_consent": value}) is False


# --- AT-35 public_only ----------------------------------------------------------


def test_private_with_consent_is_refused_by_a_public_only_peer():
    log = EvidenceLog()
    payload = manifest(visibility="private", forwarding_consent=True)
    before = copy.deepcopy(payload)

    decision = evaluate_forwarding(
        payload, now_unix=NOW, peer=PUBLIC_ONLY, evidence=log
    )

    assert decision.admitted is False
    assert decision.code == ErrorCode.PEER_REFUSES_PRIVATE.value
    assert decision.clause == "peer_public_only"
    assert decision.detail["peer_id"] == "peer-P"
    assert payload == before, "no mutation before or during refusal"

    refusals = log.of(EventCode.FORWARD_REFUSED)
    assert len(refusals) == 1
    assert refusals[0].detail["clause"] == "peer_public_only"
    assert log.of(EventCode.FORWARD_ADMITTED) == ()


def test_consent_does_not_override_public_only():
    consented = manifest(visibility="private", forwarding_consent=True)
    assert evaluate_forwarding(consented, now_unix=NOW, peer=ORDINARY).admitted is True
    assert evaluate_forwarding(consented, now_unix=NOW, peer=PUBLIC_ONLY).admitted is False


def test_public_object_reaches_a_public_only_peer():
    assert evaluate_forwarding(
        manifest(visibility="public"), now_unix=NOW, peer=PUBLIC_ONLY
    ).admitted is True


# --- forwarding admission clauses ------------------------------------------------


def test_expiry_clause_is_inclusive():
    expiring = manifest(expires_at_unix=NOW)
    assert evaluate_forwarding(expiring, now_unix=NOW - 1, peer=ORDINARY).admitted is True
    for tick in (NOW, NOW + 1):
        decision = evaluate_forwarding(expiring, now_unix=tick, peer=ORDINARY)
        assert decision.admitted is False
        assert decision.code == ErrorCode.EXPIRED.value


def test_hop_limit_clause():
    assert evaluate_forwarding(
        manifest(hop_limit=3, hop_count=2), now_unix=NOW, peer=ORDINARY
    ).admitted is True
    decision = evaluate_forwarding(
        manifest(hop_limit=3, hop_count=3), now_unix=NOW, peer=ORDINARY
    )
    assert decision.admitted is False
    assert decision.code == ErrorCode.HOP_LIMIT.value


def test_copy_budget_clause():
    assert evaluate_forwarding(
        manifest(remaining_copy_budget=1), now_unix=NOW, peer=ORDINARY
    ).admitted is True
    decision = evaluate_forwarding(
        manifest(remaining_copy_budget=0), now_unix=NOW, peer=ORDINARY
    )
    assert decision.admitted is False
    assert decision.code == ErrorCode.COPY_BUDGET.value


def test_human_confirmation_clause():
    decision = evaluate_forwarding(
        manifest(), now_unix=NOW, peer=ORDINARY, human_confirmed=False
    )
    assert decision.admitted is False
    assert decision.code == ErrorCode.HUMAN_CONFIRMATION_MISSING.value


def test_clause_order_is_deterministic_when_several_would_fail():
    """Expiry is reported first, then hop, then copy, then consent."""
    everything_wrong = manifest(
        expires_at_unix=NOW - 1,
        hop_limit=1,
        hop_count=5,
        remaining_copy_budget=0,
        visibility="private",
    )
    assert evaluate_forwarding(
        everything_wrong, now_unix=NOW, peer=PUBLIC_ONLY
    ).code == ErrorCode.EXPIRED.value

    no_expiry = dict(everything_wrong)
    no_expiry.pop("expires_at_unix")
    assert evaluate_forwarding(
        no_expiry, now_unix=NOW, peer=PUBLIC_ONLY
    ).code == ErrorCode.HOP_LIMIT.value

    no_hop = dict(no_expiry, hop_count=0, hop_limit=6)
    assert evaluate_forwarding(
        no_hop, now_unix=NOW, peer=PUBLIC_ONLY
    ).code == ErrorCode.COPY_BUDGET.value


# --- forwarding state -------------------------------------------------------------


def test_successful_forwarding_advances_state_exactly_once():
    payload = manifest(hop_count=2, remaining_copy_budget=5)
    advanced = advance_forwarding_state(payload)
    assert advanced["hop_count"] == 3
    assert advanced["remaining_copy_budget"] == 4
    assert payload["hop_count"] == 2, "original unmutated"


def test_failed_forwarding_changes_neither_value():
    payload = manifest(hop_limit=2, hop_count=2, remaining_copy_budget=4)
    before = copy.deepcopy(payload)
    decision = evaluate_forwarding(payload, now_unix=NOW, peer=ORDINARY)
    assert decision.admitted is False
    assert payload == before


def test_forwarding_state_does_not_change_object_identity():
    payload = manifest(hop_count=0, remaining_copy_budget=8)
    advanced = payload
    for _ in range(5):
        advanced = advance_forwarding_state(advanced)
    assert advanced["hop_count"] == 5
    assert advanced["remaining_copy_budget"] == 3
    assert identity_is_stable(payload, advanced)
    assert codec.identity_bytes(payload) == codec.identity_bytes(advanced)


def test_advance_refuses_to_produce_a_negative_budget():
    with pytest.raises(ProtocolError) as excinfo:
        advance_forwarding_state(manifest(remaining_copy_budget=0))
    assert excinfo.value.code is ErrorCode.COPY_BUDGET


@pytest.mark.parametrize("field", ["hop_count", "remaining_copy_budget", "hop_limit"])
@pytest.mark.parametrize("value", [-1, True, "3", 1.5, None])
def test_malformed_forwarding_state_is_schema_invalid(field, value):
    with pytest.raises(ProtocolError) as excinfo:
        evaluate_forwarding(manifest(**{field: value}), now_unix=NOW, peer=ORDINARY)
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_malformed_expiry_is_schema_invalid():
    for value in ("soon", 1.5, True, []):
        with pytest.raises(ProtocolError) as excinfo:
            evaluate_forwarding(
                manifest(expires_at_unix=value), now_unix=NOW, peer=ORDINARY
            )
        assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


#: Codes this module demonstrably reaches, used by the AT-32 coverage matrix.
REACHED_CODES = (
    ErrorCode.SCHEMA_INVALID,
    ErrorCode.PAYLOAD_TOO_LARGE,
    ErrorCode.VERSION_UNSUPPORTED,
    ErrorCode.EXPIRED,
    ErrorCode.HOP_LIMIT,
    ErrorCode.COPY_BUDGET,
    ErrorCode.CONSENT_REQUIRED,
    ErrorCode.HUMAN_CONFIRMATION_MISSING,
    ErrorCode.PEER_REFUSES_PRIVATE,
    ErrorCode.OUT_OF_BUDGET,
    ErrorCode.SNAPSHOT_INVALID,
    ErrorCode.SNAPSHOT_CORRUPTED,
    ErrorCode.STORE_LOCKED,
)


def test_each_reached_code_is_actually_reachable(tmp_path):
    """Trigger every code in REACHED_CODES, proving the matrix is honest.

    Without this, the AT-32 coverage claim would rest on a hand-written
    list that could drift from what the code can actually produce.
    """
    from shongket_core import canonical_registry, parse_schema_id
    from shongket_core.persist import SnapshotStore, StoreLock

    triggered: set[ErrorCode] = set()

    def raises(fn) -> None:
        try:
            fn()
        except ProtocolError as exc:
            triggered.add(exc.code)

    registry = canonical_registry()

    raises(lambda: read_visibility(manifest(visibility="bad")))
    raises(lambda: registry.resolve("shongket.content.v9.0"))
    raises(lambda: parse_schema_id("shongket.content.v1.0\n"))

    # PAYLOAD_TOO_LARGE: a capsule padded past the frozen 4096-byte limit.
    raises(
        lambda: registry.accept(
            {
                "schema": "shongket.capsule.v1.0",
                "capsule_id": "c" * 64,
                "object_ref": "o" * 64,
                "human_confirmed": True,
                "extracted_fields": {"summary_bn": "p" * 5000},
            }
        )
    )

    raises(lambda: FragmentStore(capacity_bytes=0).put(frag(0)))

    snap = SnapshotStore(tmp_path / "reach.json")
    raises(snap.load)  # SNAPSHOT_INVALID: nothing there

    good = FragmentStore()
    good.put(frag(0))
    snap.save(good, peer_id="peer-A", created_at_unix=NOW)

    tampered = snap.read_document()
    tampered["peer_id"] = "tampered"
    snap.path.write_bytes(codec.canonical_bytes(tampered))
    raises(snap.read_document)  # SNAPSHOT_CORRUPTED

    lock = StoreLock(snap.lock_path)
    lock.acquire()
    try:
        raises(lambda: snap.save(good, peer_id="peer-A", created_at_unix=NOW))
    finally:
        lock.release()

    # Policy refusals return a decision rather than raising.
    for payload, code, confirmed, peer in (
        (manifest(expires_at_unix=NOW), ErrorCode.EXPIRED, True, ORDINARY),
        (manifest(hop_limit=1, hop_count=1), ErrorCode.HOP_LIMIT, True, ORDINARY),
        (manifest(remaining_copy_budget=0), ErrorCode.COPY_BUDGET, True, ORDINARY),
        (manifest(visibility="private"), ErrorCode.CONSENT_REQUIRED, True, ORDINARY),
        (manifest(), ErrorCode.HUMAN_CONFIRMATION_MISSING, False, ORDINARY),
        (
            manifest(visibility="private", forwarding_consent=True),
            ErrorCode.PEER_REFUSES_PRIVATE,
            True,
            PUBLIC_ONLY,
        ),
    ):
        decision = evaluate_forwarding(
            payload, now_unix=NOW, peer=peer, human_confirmed=confirmed
        )
        assert decision.code == code.value, code
        triggered.add(code)

    missing = sorted(c.value for c in REACHED_CODES if c not in triggered)
    assert missing == [], f"claimed reachable but not triggered: {missing}"
