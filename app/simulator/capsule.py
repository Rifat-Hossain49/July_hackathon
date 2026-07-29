"""Manually supplied semantic capsule (M0).

In M0 the capsule is constructed in code; there is no AI extraction and no
UI-driven human-review flow. The capsule is built by test scenarios and the
CLI tool. The ``human_confirmed`` flag is always ``True`` in this slice;
AT-02 (human confirmation gate) is covered in a later M0 slice.
"""

from __future__ import annotations

import time

from . import hashutil


def build_capsule(
    object_id: str,
    *,
    summary_bn: str,
    event_type: str = "flood",
    urgency: str = "life_safety",
    location_text: str = "",
    required_action: str = "",
    required_resource: str = "",
    human_confirmed: bool = True,
    confirmation_method: str = "manual_form_only",
    created_at_unix: int | None = None,
) -> dict:
    """Return a Shongket v1 semantic capsule bound to ``object_id``.

    The returned dict matches the ``shongket.capsule.v1`` schema documented in
    PROTOCOL_SPEC.md §3.1. ``capsule_id`` is derived from the canonical capsule
    bytes; ``object_ref`` equals the supplied ``object_id``.

    Parameters
    ----------
    object_id:
        Shongket content object ID (SHA-256 of the original source bytes).
    summary_bn:
        Bangla summary text, up to 280 characters (enforced by validation).
    event_type, urgency:
        Enum-validated fields. ``validation.validate_payload`` rejects
        unknown values.
    human_confirmed:
        M0 always supplies ``True``; AT-02 introduces the gating logic.
    confirmation_method:
        One of ``"human_confirm"``, ``"manual_form_only"``,
        ``"ai_only_disabled"``.
    created_at_unix:
        Optional deterministic override for tests.
    """
    capsule_body: dict = {
        "schema": "shongket.capsule.v1",
        "object_ref": object_id,
        "source_media_ref": object_id,
        "extracted_fields": {
            "event_type": event_type,
            "location_text": location_text,
            "urgency": urgency,
            "affected_people": "unknown",
            "required_action": required_action,
            "required_resource": required_resource,
            "summary_bn": summary_bn,
            "summary_bn_en_mix": "",
            "media_timestamps": [],
            "keyframe_cids": [],
        },
        "uncertainty": [],
        "reviewer_did_correction": False,
        "confirmation_method": confirmation_method,
        "human_confirmed": human_confirmed,
        "creator_pub_key_id": "test-key-0",
        "signatures": [],
        "created_at_unix": int(created_at_unix if created_at_unix is not None else time.time()),
    }
    capsule_body["capsule_id"] = _capsule_id_for(capsule_body)
    return capsule_body


def _capsule_id_for(capsule_body: dict) -> str:
    """Stable capsule ID derived from the canonical capsule bytes.

    Excludes ``capsule_id`` itself when computing the hash to avoid
    self-reference. ``signatures`` and ``created_at_unix`` are excluded
    so the same logical capsule produced at different times still has a
    stable identity.
    """
    canonical = {
        "schema": capsule_body["schema"],
        "object_ref": capsule_body["object_ref"],
        "source_media_ref": capsule_body["source_media_ref"],
        "extracted_fields": capsule_body["extracted_fields"],
        "confirmation_method": capsule_body["confirmation_method"],
        "human_confirmed": capsule_body["human_confirmed"],
        "creator_pub_key_id": capsule_body["creator_pub_key_id"],
    }
    import json

    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashutil.sha256_hex(encoded)
