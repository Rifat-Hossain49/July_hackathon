"""AT-24 -- unsupported version rejected.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-24, M1, S2):

    with a registry supporting major 1 only and a known set of
    registered minors, submitting (a) a payload declaring major 2, (b) a
    payload that is both major 2 and structurally malformed, and (c) a
    payload declaring major 1 with an unregistered minor, all three are
    rejected with VERSION_UNSUPPORTED. Case (b) proves the version is
    resolved before structural parsing, so SCHEMA_INVALID is never
    returned instead. No partial decode; nothing scheduled or persisted.

Evidence required: rejection log with code and declared version.
Runtime boundary: `core/schema`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from shongket_core import (
    ErrorClass,
    ErrorCode,
    MinorCompatibility,
    ProtocolError,
    SchemaDefinition,
    SchemaRegistry,
    SchemaVersion,
    canonical_registry,
    parse_schema_id,
)


GOLDEN = json.loads(
    (Path(__file__).resolve().parent.parent / "testdata" / "golden_vectors.json")
    .read_text(encoding="utf-8")
)

CONTENT_V1 = SchemaDefinition(
    family="content",
    version=SchemaVersion(1, 0),
    required_fields=("schema", "object_id"),
)


def registry() -> SchemaRegistry:
    """Major 1 only, with 1.1 as the single registered minor."""
    return SchemaRegistry(
        definitions=(CONTENT_V1,),
        compatibilities=(MinorCompatibility("content", 1, 1),),
    )


# --- the three canonical cases ----------------------------------------------


def test_case_a_unknown_major_rejected():
    with pytest.raises(ProtocolError) as excinfo:
        registry().accept(
            {"schema": "shongket.content.v2.0", "object_id": "a" * 64}
        )
    error = excinfo.value
    assert error.code is ErrorCode.VERSION_UNSUPPORTED
    assert "2" in error.detail


def test_case_b_unknown_major_and_malformed_reports_version_not_schema():
    """The decisive case: version is resolved before structural parsing.

    This payload is *also* structurally invalid — it is missing the
    required ``object_id``. If validation ran first it would report
    SCHEMA_INVALID. It must report VERSION_UNSUPPORTED.
    """
    malformed_and_future = {
        "schema": "shongket.content.v2.0",
        "chunk_index": "not-an-integer",
        # required object_id deliberately absent
    }

    with pytest.raises(ProtocolError) as excinfo:
        registry().accept(malformed_and_future)

    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED
    assert excinfo.value.code is not ErrorCode.SCHEMA_INVALID


def test_case_c_unregistered_minor_rejected():
    with pytest.raises(ProtocolError) as excinfo:
        registry().accept(
            {"schema": "shongket.content.v1.7", "object_id": "a" * 64}
        )
    error = excinfo.value
    assert error.code is ErrorCode.VERSION_UNSUPPORTED
    assert "7" in error.detail


# --- malformed version syntax -----------------------------------------------


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN["versions"] if not c["valid"]],
    ids=[c["identifier"] or "empty" for c in GOLDEN["versions"] if not c["valid"]],
)
def test_malformed_version_identifiers_rejected(case):
    with pytest.raises(ProtocolError) as excinfo:
        parse_schema_id(case["identifier"])
    assert excinfo.value.code.value == case["error_code"]


@pytest.mark.parametrize(
    "case",
    [c for c in GOLDEN["versions"] if c["valid"]],
    ids=[c["identifier"] for c in GOLDEN["versions"] if c["valid"]],
)
def test_well_formed_version_identifiers_parse_as_committed(case):
    parsed = parse_schema_id(case["identifier"])
    assert parsed.family == case["family"]
    assert parsed.major == case["major"]
    assert parsed.minor == case["minor"]
    assert parsed.legacy_alias == case["legacy_alias"]


@pytest.mark.parametrize(
    "identifier, note",
    [
        ("shongket.content.v1.0\n", "trailing LF"),
        ("shongket.content.v1.0\r\n", "trailing CRLF"),
        ("shongket.content.v1.0\r", "trailing CR"),
        ("shongket.content.v1.0 ", "trailing space"),
        ("shongket.content.v1.0\t", "trailing tab"),
        ("\nshongket.content.v1.0", "leading LF"),
        (" shongket.content.v1.0", "leading space"),
        ("\tshongket.content.v1.0", "leading tab"),
        (" shongket.content.v1.0 ", "surrounding spaces"),
        ("shongket.content.v1\n", "legacy alias with trailing LF"),
    ],
)
def test_surrounding_whitespace_is_rejected_not_stripped(identifier, note):
    """A trailing newline must not slip through.

    Python's ``$`` also matches immediately before a trailing newline,
    so an anchored pattern would accept ``...v1.0\\n``. Two byte strings
    resolving to one schema identity would break the
    one-spelling-per-version property byte-stable serialization relies
    on, so the parser uses ``fullmatch``.
    """
    with pytest.raises(ProtocolError) as excinfo:
        parse_schema_id(identifier)
    assert excinfo.value.code is ErrorCode.VERSION_UNSUPPORTED


def test_valid_identifiers_still_parse_after_the_whitespace_fix():
    for identifier, expected_minor, legacy in (
        ("shongket.content.v1.0", 0, False),
        ("shongket.capsule.v1.0", 0, False),
        ("shongket.fragment.v1.0", 0, False),
        ("shongket.content.v1", 0, True),
        ("shongket.content.v2.13", 13, False),
    ):
        parsed = parse_schema_id(identifier)
        assert parsed.minor == expected_minor
        assert parsed.legacy_alias is legacy


def test_absent_or_non_string_schema_is_schema_invalid():
    """Not a version problem: the payload cannot be identified at all."""
    for identifier in (None, 42, [], {}, True):
        with pytest.raises(ProtocolError) as excinfo:
            parse_schema_id(identifier)
        assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_unknown_schema_family_is_schema_invalid():
    """Slice-1 choice: an unknown family is not a version failure.

    AT-24 fixes the code only for version failures. A family this
    protocol does not define at any version is a structural problem, so
    it is reported as SCHEMA_INVALID rather than VERSION_UNSUPPORTED.
    """
    with pytest.raises(ProtocolError) as excinfo:
        registry().resolve("shongket.widget.v1.0")
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


# --- no mutation on rejection ------------------------------------------------


def test_rejection_does_not_mutate_the_registry_or_the_payload():
    reg = registry()
    definitions_before = reg.definitions()
    compat_before = reg.registered_compatibilities()

    payload = {"schema": "shongket.content.v2.0", "object_id": "a" * 64}
    payload_before = dict(payload)

    for identifier in (
        "shongket.content.v2.0",
        "shongket.content.v1.7",
        "shongket.widget.v1.0",
        "shongket.content.vX",
    ):
        attempt = dict(payload, schema=identifier)
        with pytest.raises(ProtocolError):
            reg.accept(attempt)
        assert attempt == dict(payload_before, schema=identifier)

    assert reg.definitions() == definitions_before
    assert reg.registered_compatibilities() == compat_before
    assert reg == registry()


def test_rejection_is_deterministic_across_repeated_attempts():
    reg = registry()
    codes, details = [], []
    for _ in range(3):
        with pytest.raises(ProtocolError) as excinfo:
            reg.accept({"schema": "shongket.content.v2.0", "object_id": "a" * 64})
        codes.append(excinfo.value.code)
        details.append(excinfo.value.detail)
    assert len(set(codes)) == 1
    assert len(set(details)) == 1


# --- canonical error taxonomy ------------------------------------------------


def test_version_unsupported_is_terminal_and_canonical():
    with pytest.raises(ProtocolError) as excinfo:
        canonical_registry().resolve("shongket.content.v9.0")
    error = excinfo.value

    assert error.code is ErrorCode.VERSION_UNSUPPORTED
    assert error.error_class is ErrorClass.TERMINAL
    assert error.retryable is False

    evidence = error.to_dict()
    assert evidence["schema"] == "shongket.error.v1"
    assert evidence["code"] == "VERSION_UNSUPPORTED"
    assert isinstance(evidence["detail"], str) and evidence["detail"]


def test_undocumented_error_codes_cannot_be_raised():
    with pytest.raises(TypeError, match="undocumented error codes"):
        ProtocolError("MADE_UP_CODE", "nope")  # type: ignore[arg-type]


def test_every_canonical_code_has_exactly_one_classification():
    from shongket_core.errors import ERROR_CLASSES

    assert set(ERROR_CLASSES) == set(ErrorCode)
    for code, klass in ERROR_CLASSES.items():
        assert isinstance(klass, ErrorClass)
