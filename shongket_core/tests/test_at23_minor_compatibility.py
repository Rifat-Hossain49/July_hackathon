"""AT-23 -- compatible minor-version payload accepted.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-23, M1, S2):

    with a registry supporting major 1 and a registered compatibility
    entry for a higher minor, a payload declaring that minor and
    carrying one unknown additional field is accepted; the unknown field
    is ignored, not persisted and not echoed; no error is raised; known
    fields are validated normally.

Evidence required: acceptance log naming the ignored field.
Runtime boundary: `core/schema` + `core/validate`.

The strict half of D-M1-05 is asserted here too: compatibility is
*declared, never inferred*, so an unregistered minor is refused even
though it is syntactically valid and its major is supported.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest

from shongket_core import (
    ErrorCode,
    MinorCompatibility,
    ProtocolError,
    SchemaDefinition,
    SchemaRegistry,
    SchemaVersion,
    canonical_registry,
)


GOLDEN = json.loads(
    (Path(__file__).resolve().parent.parent / "testdata" / "golden_vectors.json")
    .read_text(encoding="utf-8")
)

V1_0 = SchemaVersion(1, 0)

CONTENT_V1 = SchemaDefinition(
    family="content",
    version=V1_0,
    required_fields=("schema", "object_id"),
    optional_fields=("expires_at_unix",),
)
CAPSULE_V1 = SchemaDefinition(
    family="capsule",
    version=V1_0,
    required_fields=("schema", "capsule_id"),
)


def _payload(schema: str, **extra) -> dict:
    base = {"schema": schema, "object_id": "a" * 64}
    base.update(extra)
    return base


# --- registered compatibility ------------------------------------------------


def test_registered_higher_minor_is_accepted_and_unknown_field_ignored():
    registry = SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )
    payload = _payload(
        "shongket.content.v1.1", a_field_from_the_future="ignore me"
    )

    accepted = registry.accept(payload)

    assert accepted.resolution.version == SchemaVersion(1, 1)
    assert accepted.resolution.via_registered_compatibility is True
    assert accepted.resolution.legacy_alias is False
    # The unknown field is named as evidence, and ignored.
    assert accepted.ignored_fields == ("a_field_from_the_future",)
    # Known fields were still checked.
    assert "object_id" in accepted.payload


def test_ignored_field_is_not_echoed_into_the_accepted_view():
    """AT-23: the unknown field must not be persisted or echoed."""
    registry = SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )
    accepted = registry.accept(
        _payload("shongket.content.v1.1", surprise=123)
    )

    known = accepted.resolution.definition.known_fields
    echoed = {k: v for k, v in accepted.payload.items() if k in known}
    assert "surprise" not in echoed
    assert accepted.ignored_fields == ("surprise",)


def test_baseline_and_lower_minors_need_no_registration():
    registry = SchemaRegistry(definitions=(CONTENT_V1,))

    baseline = registry.accept(_payload("shongket.content.v1.0"))
    assert baseline.resolution.version == SchemaVersion(1, 0)
    assert baseline.resolution.via_registered_compatibility is False


# --- lower minors require registration too (ratified D-M1-05) ---------------
#
# This replaces an earlier test that asserted a lower minor is always
# accepted. Ordering grants nothing: a receiver holds no record of what
# an unregistered earlier release looked like, so treating "lower" as
# "safe" would be inference, which D-M1-05 forbids.

CONTENT_V1_2 = SchemaDefinition(
    family="content", version=SchemaVersion(1, 2), required_fields=("schema",)
)


@pytest.mark.parametrize("minor", [0, 1])
def test_unregistered_lower_minor_is_rejected(minor):
    registry = SchemaRegistry(definitions=(CONTENT_V1_2,))

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve(f"shongket.content.v1.{minor}")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED
    assert "never inferred from ordering" in excinfo.value.detail


def test_registered_lower_minor_is_accepted_and_marked_compatibility_based():
    registry = SchemaRegistry(
        definitions=(CONTENT_V1_2,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )

    resolved = registry.resolve("shongket.content.v1.1")
    assert resolved.version == SchemaVersion(1, 1)
    assert resolved.via_registered_compatibility is True

    # 1.0 is still unregistered and stays refused.
    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.content.v1.0")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED


def test_exact_version_is_accepted_without_any_compatibility_entry():
    registry = SchemaRegistry(definitions=(CONTENT_V1_2,))

    resolved = registry.resolve("shongket.content.v1.2")
    assert resolved.version == SchemaVersion(1, 2)
    assert resolved.via_registered_compatibility is False
    assert resolved.legacy_alias is False


def test_lower_minor_compatibility_does_not_leak_between_families():
    registry = SchemaRegistry(
        definitions=(
            CONTENT_V1_2,
            SchemaDefinition(
                family="capsule",
                version=SchemaVersion(1, 2),
                required_fields=("schema",),
            ),
        ),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )

    assert registry.resolve("shongket.content.v1.1").via_registered_compatibility

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.capsule.v1.1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED


def test_compatibility_does_not_leak_between_majors():
    """An entry on major 1 grants nothing on major 2."""
    registry = SchemaRegistry(
        definitions=(
            CONTENT_V1_2,
            SchemaDefinition(
                family="content",
                version=SchemaVersion(2, 5),
                required_fields=("schema",),
            ),
        ),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )

    assert registry.resolve("shongket.content.v1.1").via_registered_compatibility
    assert registry.resolve("shongket.content.v2.5").via_registered_compatibility is False

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.content.v2.1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED


def test_legacy_alias_does_not_bypass_registration_when_exact_is_later():
    """`...v1` resolves to 1.0, then must still clear the same gate.

    With an exact registered version of 1.2, the alias is not a back
    door to an unregistered 1.0.
    """
    registry = SchemaRegistry(definitions=(CONTENT_V1_2,))

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.content.v1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED

    # Registering 1.0 explicitly opens the alias, still marked as
    # compatibility-based rather than exact.
    opened = SchemaRegistry(
        definitions=(CONTENT_V1_2,),
        compatibilities=(MinorCompatibility("content", 1, 0),),
    )
    resolved = opened.resolve("shongket.content.v1")
    assert resolved.version == SchemaVersion(1, 0)
    assert resolved.legacy_alias is True
    assert resolved.via_registered_compatibility is True


def test_legacy_alias_at_exact_one_point_zero_needs_no_registration():
    registry = SchemaRegistry(definitions=(CONTENT_V1,))

    resolved = registry.resolve("shongket.content.v1")
    assert resolved.version == SchemaVersion(1, 0)
    assert resolved.legacy_alias is True
    assert resolved.via_registered_compatibility is False


# --- compatibility is never inferred ----------------------------------------


def test_unregistered_higher_minor_is_rejected():
    registry = SchemaRegistry(definitions=(CONTENT_V1,))

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.content.v1.1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED
    assert "never" in excinfo.value.detail or "not registered" in excinfo.value.detail


def test_registering_one_minor_does_not_imply_another():
    """Compatibility with 1.1 says nothing about 1.2."""
    registry = SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 2),),
    )

    accepted = registry.resolve("shongket.content.v1.2")
    assert accepted.via_registered_compatibility is True

    # 1.1 sits *below* the registered 1.2 but was never itself declared.
    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.content.v1.1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED

    with pytest.raises(ProtocolError):
        registry.resolve("shongket.content.v1.3")


def test_compatibility_for_one_family_does_not_leak_to_another():
    registry = SchemaRegistry(
        definitions=(CONTENT_V1, CAPSULE_V1),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )
    assert registry.resolve("shongket.content.v1.1").via_registered_compatibility

    with pytest.raises(ProtocolError) as excinfo:
        registry.resolve("shongket.capsule.v1.1")
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED


# --- order independence ------------------------------------------------------


def test_registry_construction_order_does_not_affect_results():
    definitions = [CONTENT_V1, CAPSULE_V1]
    compat = [
        MinorCompatibility("content", 1, 1),
        MinorCompatibility("capsule", 1, 2),
    ]

    registries = [
        SchemaRegistry(definitions=list(d), compatibilities=list(c))
        for d in itertools.permutations(definitions)
        for c in itertools.permutations(compat)
    ]

    assert len(registries) == 4
    first = registries[0]
    for other in registries[1:]:
        assert other == first
        assert other.definitions() == first.definitions()
        assert other.registered_compatibilities() == first.registered_compatibilities()
        for identifier in (
            "shongket.content.v1.0",
            "shongket.content.v1.1",
            "shongket.capsule.v1.2",
        ):
            assert other.resolve(identifier) == first.resolve(identifier)


def test_duplicate_and_contradictory_registrations_are_refused():
    with pytest.raises(ValueError, match="duplicate registration"):
        SchemaRegistry(definitions=(CONTENT_V1, CONTENT_V1))

    contradictory = SchemaDefinition(
        family="content", version=V1_0, required_fields=("schema", "different")
    )
    with pytest.raises(ValueError, match="contradictory registration"):
        SchemaRegistry(definitions=(CONTENT_V1, contradictory))

    with pytest.raises(ValueError, match="duplicate compatibility"):
        SchemaRegistry(
            definitions=(CONTENT_V1,),
            compatibilities=(
                MinorCompatibility("content", 1, 1),
                MinorCompatibility("content", 1, 1),
            ),
        )


def test_compatibility_must_reference_a_registered_schema():
    with pytest.raises(ValueError, match="unregistered schema"):
        SchemaRegistry(
            definitions=(CONTENT_V1,),
            compatibilities=(MinorCompatibility("widget", 1, 1),),
        )


def test_compatibility_entry_for_the_exact_version_is_refused():
    """Registering the exact version is dead configuration, not a no-op."""
    with pytest.raises(ValueError, match="equals the exact registered version"):
        SchemaRegistry(
            definitions=(CONTENT_V1,),
            compatibilities=(MinorCompatibility("content", 1, 0),),
        )


def test_lower_minor_compatibility_entries_are_registrable():
    """The ratified rule requires lower minors to be declarable at all."""
    registry = SchemaRegistry(
        definitions=(CONTENT_V1_2,),
        compatibilities=(
            MinorCompatibility("content", 1, 0),
            MinorCompatibility("content", 1, 1),
        ),
    )
    assert registry.registered_compatibilities() == (
        MinorCompatibility("content", 1, 0),
        MinorCompatibility("content", 1, 1),
    )
    for minor in (0, 1):
        assert registry.resolve(
            f"shongket.content.v1.{minor}"
        ).via_registered_compatibility is True


def test_registry_has_no_shared_mutable_state():
    """Two canonical registries are equal but independent objects."""
    a = canonical_registry()
    b = canonical_registry()
    assert a == b
    assert a is not b


# --- legacy alias resolves to 1.0 only --------------------------------------


def test_legacy_alias_resolves_to_one_point_zero_only():
    registry = SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )

    legacy = registry.resolve("shongket.content.v1")
    assert legacy.version == SchemaVersion(1, 0)
    assert legacy.legacy_alias is True
    assert legacy.via_registered_compatibility is False

    explicit = registry.resolve("shongket.content.v1.0")
    assert legacy.version == explicit.version
    # The alias flag is the only difference between the two.
    assert explicit.legacy_alias is False


def test_legacy_alias_never_means_a_registered_higher_minor():
    """`...v1` must not drift to 1.1 just because 1.1 is registered."""
    registry = SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )
    assert registry.resolve("shongket.content.v1").version == SchemaVersion(1, 0)


def test_golden_registry_resolution_expectations():
    """Committed expectations for the canonical registry."""
    registry = canonical_registry()
    for case in GOLDEN["registry_resolution"]:
        identifier = case["identifier"]
        if case["outcome"] == "accepted":
            resolved = registry.resolve(identifier)
            assert resolved.legacy_alias == case["legacy_alias"], identifier
            assert (
                resolved.via_registered_compatibility
                == case["via_registered_compatibility"]
            ), identifier
        else:
            with pytest.raises(ProtocolError) as excinfo:
                registry.resolve(identifier)
            assert excinfo.value.code.value == case["error_code"], identifier
