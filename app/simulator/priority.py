"""Deterministic M0 priority scheduler (PROTOCOL_SPEC.md §6.0).

The seven-tier order is:

1. critical semantic capsule
2. required manifests and control data
3. non-critical semantic capsule
4. thumbnails and keyframes
5. playable previews
6. standard representations
7. original-quality fragments

This module implements the ordering and the ``expires_at`` admission
rule. ``copy_budget`` enforcement and multi-object contention remain out
of scope for M0.
"""

from __future__ import annotations

from dataclasses import dataclass


# Tier index = lower-is-higher-priority (0 is top).
TIER_CRITICAL_CAPSULE = 0
TIER_MANIFEST = 1
TIER_NONCRITICAL_CAPSULE = 2
TIER_THUMBNAIL = 3
TIER_PREVIEW = 4
TIER_STANDARD = 5
TIER_ORIGINAL = 6


# Allowed representation IDs in the M0 schema.
_REPRESENTATION_TIER: dict[str, int] = {
    "thumb": TIER_THUMBNAIL,
    "preview": TIER_PREVIEW,
    "standard": TIER_STANDARD,
    "original": TIER_ORIGINAL,
}


@dataclass(frozen=True)
class SchedulerItem:
    """A single transferable unit considered by the scheduler."""

    object_id: str
    representation_id: str | None  # None for capsule and manifest tiers
    chunk_index: int | None
    tier: int
    urgency: str = "life_safety"  # for the capsule tier only

    @classmethod
    def capsule(cls, *, object_id: str, capsule_id: str, urgency: str = "life_safety") -> "SchedulerItem":
        if urgency == "life_safety":
            tier = TIER_CRITICAL_CAPSULE
        else:
            tier = TIER_NONCRITICAL_CAPSULE
        return cls(
            object_id=object_id,
            representation_id=f"capsule:{capsule_id}",
            chunk_index=None,
            tier=tier,
            urgency=urgency,
        )

    @classmethod
    def manifest(cls, *, object_id: str, manifest_id: str) -> "SchedulerItem":
        return cls(
            object_id=object_id,
            representation_id=f"manifest:{manifest_id}",
            chunk_index=None,
            tier=TIER_MANIFEST,
        )

    @classmethod
    def chunk(cls, *, object_id: str, representation_id: str, chunk_index: int) -> "SchedulerItem":
        if representation_id not in _REPRESENTATION_TIER:
            raise ValueError(f"unknown representation_id: {representation_id!r}")
        return cls(
            object_id=object_id,
            representation_id=representation_id,
            chunk_index=chunk_index,
            tier=_REPRESENTATION_TIER[representation_id],
        )


def order(items: list[SchedulerItem]) -> list[SchedulerItem]:
    """Stable sort: ascending tier; chunks then ascending ``chunk_index``.

    Within a tier, chunks for the same representation are emitted in
    ``chunk_index`` order, then ``object_id`` order, to keep the output
    deterministic across runs.
    """

    def sort_key(it: SchedulerItem) -> tuple:
        return (it.tier, it.chunk_index if it.chunk_index is not None else -1, it.representation_id or "", it.object_id)

    return sorted(items, key=sort_key)


# --- expiry admission (AT-11) ------------------------------------------------


def is_expired(*, expires_at_unix: int | None, now_unix: int) -> bool:
    """Return ``True`` when ``now_unix`` has reached or passed expiry.

    ``expires_at_unix is None`` means the object never expires.

    The boundary is **inclusive**: an object is expired at exactly
    ``now_unix == expires_at_unix``. PROTOCOL_SPEC.md §7 models this as
    ``Persisted --> Expiring: expires_at reached``, and the M0 forwarding
    policy admits an object only when it is "not expired".

    ``now_unix`` is a deterministic simulator tick supplied by the
    caller. No wall-clock is consulted anywhere in this module.
    """
    if expires_at_unix is None:
        return False
    return now_unix >= expires_at_unix


def admit_for_forwarding(
    items: list[SchedulerItem],
    *,
    expires_at_unix: int | None,
    now_unix: int,
) -> list[SchedulerItem]:
    """Return the ordered forwarding queue for ``items``.

    Returns an **empty** queue when the object is expired: expired
    content never enters the forwarding queue, so it can never be
    selected for transmission (PROTOCOL_SPEC.md §6 factor 6, and the M0
    policy "accept to forward iff: not expired, ...").

    This is an admission rule for *forwarding* only. It does not delete
    anything: an expired object already held locally stays in the store,
    because no canonical M0 document requires deletion.
    """
    if is_expired(expires_at_unix=expires_at_unix, now_unix=now_unix):
        return []
    return order(items)
