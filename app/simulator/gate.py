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

Future gates (signed payload, expired, oversized) will be added in
later slices. This module is the home for them.
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