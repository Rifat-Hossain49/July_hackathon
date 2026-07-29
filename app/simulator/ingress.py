"""Validated scheduler-ingress boundary (M0).

AT-20 requires that a malformed payload is rejected before both
**persistence** and **scheduling**. ``validation.validate_payload`` is
already enforced at the storage boundary (``store.put_chunk``); this
module adds the symmetric enforcement at the scheduler boundary.

``SchedulerIngress`` owns an in-process FIFO queue. Every admission
runs the supplied payload through ``validation.validate_payload`` and
only appends to the queue if validation succeeds. A failed admission
raises ``validation.ProtocolError`` and leaves the queue length
unchanged. Nothing is scheduled, nothing is persisted, and no event
is emitted at this boundary — callers remain responsible for their
own event-log emission.

The boundary is intentionally a thin wrapper around an existing list
so that no scheduler policy is changed; ``priority.order`` continues
to operate on the same ``SchedulerItem`` values once they have been
admitted.
"""

from __future__ import annotations

from . import priority, validation


class SchedulerIngress:
    """FIFO queue that validates payloads before they are scheduled.

    Parameters
    ----------
    kind_to_schema:
        Optional mapping from a payload-kind label (e.g. ``"capsule"``,
        ``"manifest"``, ``"fragment"``) to a schema name accepted by
        ``validation.validate_payload``. When omitted, every admission
        must supply a ``payload`` whose ``"schema"`` field is one of
        the registered schemas and the boundary validates against that
        declared schema.
    """

    def __init__(self, *, kind_to_schema: dict[str, str] | None = None) -> None:
        self._queue: list[priority.SchedulerItem] = []
        self._kinds = dict(kind_to_schema) if kind_to_schema else {}

    # -- introspection -----------------------------------------------------

    def __len__(self) -> int:
        return len(self._queue)

    def snapshot(self) -> list[priority.SchedulerItem]:
        """Return a copy of the current queue contents for state comparisons."""
        return list(self._queue)

    def queue_length(self) -> int:
        return len(self._queue)

    # -- admission ---------------------------------------------------------

    def admit(
        self,
        item: priority.SchedulerItem,
        *,
        payload: dict | None = None,
        kind: str | None = None,
    ) -> priority.SchedulerItem:
        """Validate ``payload`` and append ``item`` to the queue.

        Parameters
        ----------
        item:
            The scheduler item to enqueue.
        payload:
            The dict payload to validate. Required when validating
            against a schema; the boundary looks up ``payload["schema"]``
            or the ``kind``-mapped schema name.
        kind:
            Optional override for which schema name to validate against.
            If supplied, must be present in ``kind_to_schema`` or be one
            of the registered schemas in ``validation._SUPPORTED_SCHEMAS``.

        Returns
        -------
        priority.SchedulerItem
            The admitted item (identical to ``item``).

        Raises
        ------
        validation.ProtocolError
            With ``code == "SCHEMA_INVALID"`` when the payload fails
            validation. The queue is not mutated.
        """
        if payload is None:
            raise validation.ProtocolError(
                "SCHEMA_INVALID",
                "ingress requires a payload to validate",
                object_id=item.object_id,
            )

        schema_name = self._resolve_schema(payload, kind)
        validation.validate_payload(schema_name, payload)
        self._queue.append(item)
        return item

    def drain(self) -> list[priority.SchedulerItem]:
        """Remove and return every admitted item. Used by tests and the driver."""
        items = self._queue
        self._queue = []
        return items

    # -- internal ----------------------------------------------------------

    def _resolve_schema(self, payload: dict, kind: str | None) -> str:
        declared = payload.get("schema") if isinstance(payload, dict) else None
        if kind is not None and kind in self._kinds:
            return self._kinds[kind]
        if isinstance(declared, str):
            return declared
        # Final fallback: a kind supplied without a mapping and no
        # ``schema`` field on the payload. Reject explicitly.
        raise validation.ProtocolError(
            "SCHEMA_INVALID",
            "cannot determine schema name for ingress admission",
            object_id=payload.get("object_id") if isinstance(payload, dict) else None,
        )
