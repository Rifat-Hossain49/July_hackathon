"""Shongket platform-neutral deterministic core (Milestone 1).

Authorised by ``IMPLEMENTATION_STATUS: APPROVED_FOR_MILESTONE_1`` and
scoped by ``M1_SCOPE_FREEZE.md``. Standard library only: this package
must never import from ``adapters/``, from ``app.simulator``, or from
any third-party distribution (``SYSTEM_ARCHITECTURE.md`` §3.4).

Milestone 1 is complete: canonical serialization, versioning, durable
persistence, migration, policy, storage and deterministic evidence live
in this package. The authorized M2 process slice adds canonical capability
negotiation here so every adapter consumes the same decision.

The M0 simulator under ``app/simulator`` remains frozen and continues to
use its own validation boundary.
"""

from __future__ import annotations

from . import codec
from .capabilities import (
    MAX_TRANSPORT_PAYLOAD,
    NegotiatedCapabilities,
    NegotiationResult,
    PeerCapabilities,
    ensure_payload_fits,
    negotiate_capabilities,
)
from .errors import ErrorClass, ErrorCode, ProtocolError, classify
from .schema import (
    AcceptedPayload,
    MinorCompatibility,
    Resolution,
    SchemaDefinition,
    SchemaRegistry,
)
from .version import SchemaId, SchemaVersion, parse_schema_id

__all__ = [
    "ErrorClass",
    "ErrorCode",
    "ProtocolError",
    "classify",
    "MAX_TRANSPORT_PAYLOAD",
    "PeerCapabilities",
    "NegotiatedCapabilities",
    "NegotiationResult",
    "negotiate_capabilities",
    "ensure_payload_fits",
    "SchemaVersion",
    "SchemaId",
    "parse_schema_id",
    "SchemaDefinition",
    "MinorCompatibility",
    "SchemaRegistry",
    "Resolution",
    "AcceptedPayload",
    "canonical_registry",
    "codec",
]

#: Baseline version for every canonical family at Milestone 1.
_V1_0 = SchemaVersion(major=1, minor=0)


def canonical_registry() -> SchemaRegistry:
    """Build the canonical M1 registry.

    A fresh, immutable registry is returned on every call so no shared
    mutable state can leak between callers or tests.

    Field lists mirror ``PROTOCOL_SPEC.md`` §3. ``visibility``,
    ``forwarding_consent``, ``hop_count`` and ``remaining_copy_budget``
    are declared as *known optional* fields on the content manifest so a
    payload carrying them is not misreported as containing unknown
    fields. Slice 1 only recognises them; enforcing the privacy,
    consent, hop and copy rules is Slice 4.
    """
    return SchemaRegistry(
        definitions=(
            SchemaDefinition(
                family="capsule",
                version=_V1_0,
                required_fields=(
                    "schema",
                    "capsule_id",
                    "object_ref",
                    "human_confirmed",
                ),
                size_limit_bytes=4 * 1024,
                optional_fields=(
                    "source_media_ref",
                    "extracted_fields",
                    "uncertainty",
                    "reviewer_did_correction",
                    "confirmation_method",
                    "creator_pub_key_id",
                    "signatures",
                    "created_at_unix",
                ),
            ),
            SchemaDefinition(
                family="content",
                version=_V1_0,
                required_fields=(
                    "schema",
                    "object_id",
                    "capsule_ref",
                    "representations",
                    "priority",
                    "created_at_unix",
                    "hop_limit",
                    "copy_budget",
                ),
                size_limit_bytes=32 * 1024,
                optional_fields=(
                    "manifest_id",
                    "expires_at_unix",
                    "signatures",
                    "visibility",
                    "forwarding_consent",
                    "hop_count",
                    "remaining_copy_budget",
                ),
            ),
            SchemaDefinition(
                family="fragment",
                version=_V1_0,
                required_fields=(
                    "schema",
                    "object_id",
                    "representation_id",
                    "chunk_index",
                    "chunk_size",
                    "byte_range",
                    "hash",
                ),
                size_limit_bytes=512,
                optional_fields=("signature",),
            ),
        ),
    )
