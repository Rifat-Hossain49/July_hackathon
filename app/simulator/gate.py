"""M0 policy gates (slice 2).

This module hosts the higher-level policy gates that sit on top of
``validation.validate_payload``. The schema validator is responsible for
type / enum / size rules (AT-20); the gate layer is responsible for
"may this payload enter the scheduler and the transport?" decisions.

Slice 2 ships exactly one gate:

* ``capsule_human_confirmation`` (AT-02): a ``shongket.capsule.v1``
  payload that passes schema validation is still rejected at the gate
  boundary when ``human_confirmed`` is ``False``. The rejection must:

  - raise ``ProtocolError`` with ``code == "HUMAN_CONFIRMATION_MISSING"``;
  - emit a deterministic ``CAPSULE_REJECTED`` event with a stable
    ``detail`` mapping;
  - not mutate the scheduler queue or the storage map.

The gate is a pure function over a payload dict plus a logger. The
driver (``transfer.run_encounter`` and the new helpers) is responsible
for invoking the gate before scheduling or persisting the capsule.

Slice 4 adds three more gates:

* ``manual_form_fallback`` (AT-15): when the offline model is disabled,
  unavailable, failed or low-confidence, return the structured manual
  form instead. No model is ever loaded or called in M0.
* ``private_content_consent`` (AT-16): a private object may not be
  forwarded without explicit consent.
* ``payload_size_gate`` (AT-17): a payload larger than its canonical
  serialized limit is refused with ``PAYLOAD_TOO_LARGE``.

Every gate is a pure function over a payload dict plus a logger, and
every gate refuses *before* the caller schedules, transmits or
persists anything.
"""

from __future__ import annotations

from . import events, validation


def capsule_human_confirmation(
    payload: dict,
    *,
    logger: events.EventLogger,
    sender_id: str,
    receiver_id: str,
) -> None:
    """Gate a ``shongket.capsule.v1`` payload on ``human_confirmed``.

    Parameters
    ----------
    payload:
        Capsule dict. Must already pass schema validation. This gate
        does not re-run schema validation; the driver is expected to
        invoke ``validation.validate_payload`` first.
    logger:
        Event logger used to emit a deterministic ``CAPSULE_REJECTED``
        event on rejection.
    sender_id, receiver_id:
        Identifying peer IDs for the rejection event.

    Raises
    ------
    validation.ProtocolError
        With ``code == "HUMAN_CONFIRMATION_MISSING"`` when the capsule
        was not human-confirmed. The rejection event is emitted before
        the exception is raised.

    Notes
    -----
    The function is a no-op when ``human_confirmed`` is ``True``. It
    emits no event in that case; the caller emits the standard
    ``CAPSULE_DELIVERED`` event after successful delivery.
    """
    if not isinstance(payload, dict):
        raise validation.ProtocolError(
            "HUMAN_CONFIRMATION_MISSING",
            "capsule payload is not an object",
            object_id=None,
        )
    if bool(payload.get("human_confirmed")):
        return

    object_ref = payload.get("object_ref")
    capsule_id = payload.get("capsule_id")
    logger.advance(1)
    logger.emit(
        events.EventType.CAPSULE_REJECTED,
        sender_id=sender_id,
        receiver_id=receiver_id,
        object_id=object_ref,
        representation_id=f"capsule:{capsule_id}" if capsule_id else None,
        detail={
            "reason": "human_confirmed_false",
            "code": "HUMAN_CONFIRMATION_MISSING",
            "confirmation_method": payload.get("confirmation_method"),
        },
    )
    raise validation.ProtocolError(
        "HUMAN_CONFIRMATION_MISSING",
        "capsule was not human-confirmed",
        object_id=object_ref,
    )


# ---------------------------------------------------------------------------
# AT-15 -- offline-model fallback to the structured manual form (D-011).
# ---------------------------------------------------------------------------

# Canonical model conditions. ACCEPTANCE_TESTS.md AT-15 names "model
# disabled or low-confidence"; D-011 names "unavailable or too slow";
# SYSTEM_ARCHITECTURE.md names "Model failure". All four route to the
# same manual form, which is the only capsule source that exists in M0.
MODEL_DISABLED = "disabled"
MODEL_UNAVAILABLE = "unavailable"
MODEL_FAILED = "failed"
MODEL_LOW_CONFIDENCE = "low_confidence"

_FALLBACK_MODEL_STATES = frozenset(
    {MODEL_DISABLED, MODEL_UNAVAILABLE, MODEL_FAILED, MODEL_LOW_CONFIDENCE}
)

# The structured manual form. Fields mirror ``extracted_fields`` in the
# canonical SemanticCapsule (PROTOCOL_SPEC.md §3.1) so that what a human
# types maps one-to-one onto the capsule schema.
MANUAL_FORM_FIELDS: tuple[str, ...] = (
    "event_type",
    "location_text",
    "urgency",
    "affected_people",
    "required_action",
    "required_resource",
    "summary_bn",
)

# Content provenance labels (AT-15 requirement: manual, AI-generated and
# unavailable AI output must be distinguishable). M0 only ever produces
# ``manual_form``; ``ai_draft`` exists as a label so later milestones can
# mark model output without redefining the vocabulary.
SOURCE_MANUAL_FORM = "manual_form"
SOURCE_AI_DRAFT = "ai_draft"


class ManualFormRequired(dict):
    """The structured manual form returned when no model output exists.

    A plain dict subclass so it serializes canonically. Carries the
    empty form plus the reason it was presented. ``ai_output`` is always
    ``None`` in M0: no model ran, so there is nothing to report, and
    fabricating a summary here would violate D-012 and AGENTS.md
    ("do not silently replace original media with generated content").
    """


def manual_form_fallback(
    *,
    model_state: str,
    logger: events.EventLogger,
    sender_id: str,
    receiver_id: str,
    object_id: str | None = None,
) -> ManualFormRequired:
    """Return the structured manual form for a capsule draft (AT-15).

    M0 never loads, downloads or calls a model. ``model_state`` merely
    *declares* the canonical condition; this function then presents the
    manual form and emits deterministic fallback evidence.

    Raises
    ------
    validation.ProtocolError
        With ``code == "SCHEMA_INVALID"`` when ``model_state`` is not a
        recognised condition. An unknown state is a programming error,
        not a model failure, and must not silently pass.

    Notes
    -----
    A model condition is never fatal: this returns normally for every
    recognised state, so a disabled or failed model can never crash the
    simulator or block manual entry.
    """
    if model_state not in _FALLBACK_MODEL_STATES:
        raise validation.ProtocolError(
            "SCHEMA_INVALID",
            f"unknown model_state {model_state!r}; expected one of "
            f"{sorted(_FALLBACK_MODEL_STATES)}",
            object_id=object_id,
        )

    form = ManualFormRequired(
        {
            "schema": "shongket.manualform.v1",
            "model_state": model_state,
            "content_source": SOURCE_MANUAL_FORM,
            "ai_output": None,
            "fields": {name: "" for name in MANUAL_FORM_FIELDS},
        }
    )

    logger.advance(1)
    logger.emit(
        events.EventType.MODEL_FALLBACK,
        sender_id=sender_id,
        receiver_id=receiver_id,
        object_id=object_id,
        detail={
            "reason": "model_unavailable",
            "model_state": model_state,
            "content_source": SOURCE_MANUAL_FORM,
            "ai_output_present": False,
            "confirmation_method": "manual_form_only",
            "form_fields": list(MANUAL_FORM_FIELDS),
        },
    )
    return form


# ---------------------------------------------------------------------------
# AT-16 -- private-content consent gate.
# ---------------------------------------------------------------------------

# Canonical basis, and its limit. PROTOCOL_SPEC.md §8 states "Private
# content forwarding | explicit consent required"; ACCEPTANCE_TESTS.md
# AT-16 gives the precondition "private marker" and the expectation
# "refused unless explicit consent"; RISK_REGISTER.md R-11 calls for an
# "explicit consent gate per object class"; AGENTS.md requires user
# confirmation "before publicly forwarding private content".
#
# No canonical schema in PROTOCOL_SPEC.md §3 yet declares the field
# *names* that carry the marker and the consent, and PRODUCT_DECISIONS.md
# lists "Private versus public content encryption" as still open. The two
# manifest-level booleans below are therefore the minimal encoding of the
# stated rule, chosen to match the canonical wording rather than to
# invent policy. M1 schema-freezing should confirm the names.
FIELD_PRIVATE = "private"
FIELD_FORWARDING_CONSENT = "forwarding_consent"


def is_private(manifest_payload: dict) -> bool:
    """Return the object's private marker, defaulting to public."""
    return manifest_payload.get(FIELD_PRIVATE) is True


def private_content_consent(
    manifest_payload: dict,
    *,
    logger: events.EventLogger,
    sender_id: str,
    receiver_id: str,
) -> None:
    """Gate forwarding of a private object on explicit consent (AT-16).

    Public objects pass straight through: the gate must not block
    ordinary content. A private object passes only when
    ``forwarding_consent`` is exactly ``True``; a missing, false or
    malformed consent value is refused.

    "Explicit" is read strictly: the value must be the boolean ``True``.
    Truthy stand-ins such as ``"yes"`` or ``1`` are refused, because a
    consent decision recorded in an ambiguous type is not evidence that
    a human consented.

    Raises
    ------
    validation.ProtocolError
        With ``code == "CONSENT_REQUIRED"``. The refusal event is
        emitted before the exception is raised, and the caller must not
        have scheduled, transmitted or persisted anything yet.
    """
    if not isinstance(manifest_payload, dict):
        raise validation.ProtocolError(
            "CONSENT_REQUIRED", "manifest payload is not an object"
        )
    if not is_private(manifest_payload):
        return

    consent = manifest_payload.get(FIELD_FORWARDING_CONSENT)
    if consent is True:
        return

    if consent is None:
        reason = "consent_missing"
    elif consent is False:
        reason = "consent_false"
    else:
        reason = "consent_malformed"

    object_id = manifest_payload.get("object_id")
    logger.advance(1)
    logger.emit(
        events.EventType.CONSENT_REJECTED,
        sender_id=sender_id,
        receiver_id=receiver_id,
        object_id=object_id,
        detail={
            "reason": reason,
            "code": "CONSENT_REQUIRED",
            "private": True,
            "forwarding_consent": consent if isinstance(consent, bool) else None,
            "consent_type": type(consent).__name__,
        },
    )
    raise validation.ProtocolError(
        "CONSENT_REQUIRED",
        f"private object refused: {reason}",
        object_id=object_id,
    )


# ---------------------------------------------------------------------------
# AT-17 -- oversized-payload gate.
# ---------------------------------------------------------------------------


def payload_size_gate(
    kind: str,
    payload: dict,
    *,
    logger: events.EventLogger,
    sender_id: str,
    receiver_id: str,
) -> None:
    """Refuse a payload above its canonical serialized size limit (AT-17).

    Delegates the measurement to ``validation.validate_payload``, which
    performs the size check before parsing, and adds the deterministic
    ``PAYLOAD_REJECTED`` evidence event. Only ``PAYLOAD_TOO_LARGE`` is
    handled here; schema failures propagate untouched so AT-20 keeps its
    own boundary and evidence.
    """
    try:
        validation.validate_payload(kind, payload)
    except validation.ProtocolError as exc:
        if exc.code != "PAYLOAD_TOO_LARGE":
            raise
        encoded_len = len(validation.canonical_bytes(payload))
        logger.advance(1)
        logger.emit(
            events.EventType.PAYLOAD_REJECTED,
            sender_id=sender_id,
            receiver_id=receiver_id,
            object_id=payload.get("object_id"),
            detail={
                "reason": "payload_too_large",
                "code": exc.code,
                "kind": kind,
                "encoded_bytes": encoded_len,
                "limit_bytes": validation.size_limit_for(kind),
            },
        )
        raise