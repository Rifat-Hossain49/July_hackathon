"""AT-22 -- canonical serialization is byte-stable.

Acceptance criterion (ACCEPTANCE_TESTS.md AT-22, M1, S2):

    a populated object of each canonical schema is encoded, decoded and
    re-encoded; both encodings are byte-identical, key order and
    separators are stable, there is no float-formatting divergence, and
    the result is identical across processes.

Evidence required: SHA-256 of each encoding, per schema.
Runtime boundary: `core/codec`.

Expected bytes and hashes come from ``testdata/golden_vectors.json``,
which was computed independently of ``shongket_core`` from the canonical
rules in PROTOCOL_SPEC.md. The tests below compare implementation output
against those committed values; they never regenerate them.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from shongket_core import ErrorCode, ProtocolError, codec


GOLDEN_PATH = Path(__file__).resolve().parent.parent / "testdata" / "golden_vectors.json"


def _golden() -> dict:
    with GOLDEN_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


GOLDEN = _golden()
SERIALIZATION_VECTORS = GOLDEN["serialization"]


def _vector(name: str) -> dict:
    return next(v for v in SERIALIZATION_VECTORS if v["name"] == name)


# --- golden vectors ----------------------------------------------------------


@pytest.mark.parametrize(
    "vector", SERIALIZATION_VECTORS, ids=[v["name"] for v in SERIALIZATION_VECTORS]
)
def test_encoding_matches_committed_golden_vector(vector):
    produced = codec.canonical_text(vector["value"])
    assert produced == vector["canonical_text"]
    assert codec.canonical_bytes(vector["value"]).decode("utf-8") == produced
    assert len(codec.canonical_bytes(vector["value"])) == vector["byte_length"]
    assert codec.sha256_hex(codec.canonical_bytes(vector["value"])) == vector["sha256"]


def test_canonical_rules_recorded_in_golden_file_match_the_implementation():
    """The committed file states the rules the codec claims to follow."""
    rules = GOLDEN["canonical_rules"]
    assert rules["sort_keys"] is True
    assert rules["separators"] == [",", ":"]
    assert rules["ensure_ascii"] is True
    assert rules["encoding"] == "utf-8"
    assert rules["floats_allowed"] is False
    assert rules["non_string_keys_allowed"] is False

    # ensure_ascii=True is observable: non-ASCII is escaped, so the
    # canonical text is pure ASCII.
    non_ascii = _vector("capsule_non_ascii")
    produced = codec.canonical_text(non_ascii["value"])
    assert produced.isascii()
    assert "\\u" in produced


# --- stability ---------------------------------------------------------------


@pytest.mark.parametrize(
    "vector", SERIALIZATION_VECTORS, ids=[v["name"] for v in SERIALIZATION_VECTORS]
)
def test_repeated_serialization_is_identical(vector):
    first = codec.canonical_bytes(vector["value"])
    second = codec.canonical_bytes(vector["value"])
    assert first == second


@pytest.mark.parametrize(
    "vector", SERIALIZATION_VECTORS, ids=[v["name"] for v in SERIALIZATION_VECTORS]
)
def test_parse_then_reserialize_is_identical(vector):
    encoded = codec.canonical_bytes(vector["value"])
    decoded = codec.decode(encoded)
    assert codec.canonical_bytes(decoded) == encoded


def test_insertion_order_does_not_affect_output():
    """Key order is a property of the value, not of how it was built."""
    ordered = _vector("content_v1_0")
    scrambled = _vector("content_v1_0_scrambled_insertion_order")

    assert list(ordered["value"]) != list(scrambled["value"]), (
        "fixture must actually differ in insertion order"
    )
    assert codec.canonical_bytes(ordered["value"]) == codec.canonical_bytes(
        scrambled["value"]
    )
    assert ordered["sha256"] == scrambled["sha256"]


def test_serialization_is_identical_in_a_fresh_process():
    """AT-22 requires cross-process stability, not just in-process."""
    vector = _vector("content_v1_0")
    script = (
        "import json,sys;"
        "sys.path.insert(0, sys.argv[1]);"
        "from shongket_core import codec;"
        "v=json.loads(sys.argv[2]);"
        "print(codec.sha256_hex(codec.canonical_bytes(v)))"
    )
    repo_root = str(GOLDEN_PATH.resolve().parent.parent.parent)
    result = subprocess.run(
        [sys.executable, "-c", script, repo_root, json.dumps(vector["value"])],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == vector["sha256"]


def test_no_clock_or_environment_dependence():
    """Two encodings separated by real elapsed time are identical."""
    import time

    vector = _vector("capsule_v1_0")
    first = codec.canonical_bytes(vector["value"])
    start = time.time()
    while time.time() - start < 1.05:
        pass
    assert codec.canonical_bytes(vector["value"]) == first


# --- identity bytes ----------------------------------------------------------


def test_identity_bytes_exclude_forwarding_state():
    entry = GOLDEN["identity"][0]
    payload = entry["payload"]

    assert "hop_count" in payload and "remaining_copy_budget" in payload
    produced = codec.identity_bytes(payload)

    assert produced.decode("utf-8") == entry["canonical_text"]
    assert codec.sha256_hex(produced) == entry["sha256"]
    # Identity is unchanged by forwarding: it equals the manifest that
    # never carried forwarding state at all.
    assert entry["sha256"] == _vector(entry["equals_vector"])["sha256"]


def test_identity_bytes_unchanged_as_forwarding_state_advances():
    entry = GOLDEN["identity"][0]
    base = dict(entry["payload"])
    baseline = codec.identity_bytes(base)

    for hops in range(0, 5):
        moved = dict(base)
        moved["hop_count"] = hops
        moved["remaining_copy_budget"] = 8 - hops
        assert codec.identity_bytes(moved) == baseline


def test_identity_can_exclude_a_self_referential_field():
    payload = {"schema": "shongket.content.v1.0", "manifest_id": "x" * 64, "a": 1}
    reduced = codec.identity_bytes(payload, exclude=("manifest_id",))
    assert b"manifest_id" not in reduced
    assert codec.decode(reduced) == {"schema": "shongket.content.v1.0", "a": 1}


# --- strictness: no silent coercion -----------------------------------------


@pytest.mark.parametrize(
    "value, note",
    [
        (1.5, "float"),
        ({"a": 2.0}, "nested float"),
        ([1, 2.5], "float in list"),
        ({1: "a"}, "non-string key"),
        ({"a": (1, 2)}, "tuple"),
        ({"a": {1, 2}}, "set"),
        ({"a": b"bytes"}, "bytes"),
        (float("nan"), "NaN"),
        (float("inf"), "Infinity"),
    ],
)
def test_non_canonical_values_are_rejected(value, note):
    with pytest.raises(ProtocolError) as excinfo:
        codec.canonical_bytes(value)
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_booleans_and_integers_stay_distinct():
    """`1` must never serialize as `true`, nor `true` as `1`."""
    assert codec.canonical_text({"a": True}) == '{"a":true}'
    assert codec.canonical_text({"a": 1}) == '{"a":1}'
    assert codec.canonical_text({"a": True}) != codec.canonical_text({"a": 1})


def test_integer_second_timestamps_are_stable():
    assert codec.canonical_text({"created_at_unix": 1700000000}) == (
        '{"created_at_unix":1700000000}'
    )
    # A float-valued timestamp is refused rather than truncated.
    with pytest.raises(ProtocolError):
        codec.canonical_bytes({"created_at_unix": 1700000000.0})


@pytest.mark.parametrize(
    "text, note",
    [
        ("{1.5: 1}", "malformed"),
        ('{"a": 1.5}', "float literal in input"),
        ('{"a": NaN}', "NaN constant"),
        ('{"a": Infinity}', "Infinity constant"),
        ("{not json}", "not JSON"),
        ("", "empty"),
    ],
)
def test_decode_rejects_non_canonical_input(text, note):
    with pytest.raises(ProtocolError) as excinfo:
        codec.decode(text)
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_decode_rejects_invalid_utf8():
    with pytest.raises(ProtocolError) as excinfo:
        codec.decode(b"\xff\xfe{}")
    assert excinfo.value.code is ErrorCode.SCHEMA_INVALID


def test_rejection_reports_the_offending_path():
    with pytest.raises(ProtocolError) as excinfo:
        codec.canonical_bytes({"outer": {"inner": [0, 1.5]}})
    assert "outer.inner[1]" in excinfo.value.detail
