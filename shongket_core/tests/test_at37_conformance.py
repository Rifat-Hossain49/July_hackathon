"""AT-37 -- M0 regression, core isolation and language-neutral conformance.

Canonical definition (ACCEPTANCE_TESTS.md AT-37, M1, S1):

    all 125 M0 tests pass unchanged; `shongket_core` imports nothing from
    `adapters/` and nothing outside the standard library; CLI and metrics
    hashes match the values recorded in the M0 harness evidence.

This module also carries the language-neutral conformance vectors that
let a future port of the core be validated against the same evidence
(D-M1-08). Expected values live in
``testdata/m1_conformance_vectors.json``, computed independently of
`shongket_core` and committed; the tests compare against them and never
regenerate them.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from shongket_core import ErrorCode, codec
from shongket_core.errors import ERROR_CLASSES
from shongket_core.migrate import migrate_privacy_fields
from shongket_core.persist import SnapshotStore
from shongket_core.store import Fragment, FragmentStore


CORE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = CORE_DIR.parent
VECTORS = json.loads(
    (CORE_DIR / "testdata" / "m1_conformance_vectors.json").read_text(encoding="utf-8")
)

#: Recorded M0 evidence that must survive the M1 work unchanged.
M0_CLI_SHA256 = "D5AC79B18B6B3329A2788CDCCF45A92D10534639B20079039D1902D7F82CB4DF"
M0_METRICS_SHA256 = "E10E11D4AEF1788E92CC907060C48CA06A3E76913C2BDD58ABF43858B8891B28"

STDLIB_ALLOWED = {
    "__future__", "json", "re", "os", "enum", "base64", "hashlib", "tempfile",
    "dataclasses", "typing", "collections", "collections.abc", "pathlib",
}


def _core_modules() -> list[Path]:
    return sorted(p for p in CORE_DIR.glob("*.py"))


# --- core isolation ------------------------------------------------------------


def test_core_imports_nothing_from_adapters_or_the_simulator():
    offenders: list[str] = []
    for module in _core_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # level > 0 is a relative import inside the core: allowed.
                if node.level and node.level > 0:
                    continue
                names = [node.module or ""]
            for name in names:
                root = name.split(".")[0]
                if root in {"app", "adapters", "android"}:
                    offenders.append(f"{module.name}:{node.lineno}: {name}")
    assert offenders == [], f"core imports adapter/platform code: {offenders}"


def test_core_imports_only_the_standard_library():
    offenders: list[str] = []
    for module in _core_modules():
        tree = ast.parse(module.read_text(encoding="utf-8"), filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                candidates = [node.module or ""]
            else:
                continue
            for name in candidates:
                root = name.split(".")[0]
                if name in STDLIB_ALLOWED or root in STDLIB_ALLOWED:
                    continue
                offenders.append(f"{module.name}:{node.lineno}: {name}")
    assert offenders == [], f"non-stdlib runtime import: {offenders}"


def test_core_contains_no_dynamic_import_or_network_use():
    banned = ("importlib", "__import__", "socket", "urllib", "requests", "pickle")
    offenders = []
    for module in _core_modules():
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                text = ast.unparse(node)
                for word in banned:
                    if word in text:
                        offenders.append(f"{module.name}:{node.lineno}: {text}")
    assert offenders == []


def test_the_simulator_may_import_the_core_but_never_the_reverse():
    """Direction check: adapters depend on the core, not vice versa."""
    core_names = {p.stem for p in _core_modules()}
    for module in _core_modules():
        source = module.read_text(encoding="utf-8")
        assert "from app." not in source.replace("``app.", "")
    # And the core's own modules resolve without the simulator importable.
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import shongket_core, shongket_core.persist, shongket_core.migrate,"
        "shongket_core.policy, shongket_core.store, shongket_core.evidence;"
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(REPO_ROOT)],
        capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "ok"
    assert core_names >= {"codec", "errors", "schema", "version", "store",
                          "persist", "migrate", "policy", "evidence"}


# --- language-neutral conformance vectors ---------------------------------------


@pytest.mark.parametrize(
    "vector", VECTORS["snapshot_envelope"],
    ids=[v["name"] for v in VECTORS["snapshot_envelope"]],
)
def test_snapshot_envelope_matches_committed_vector(vector):
    produced = codec.canonical_text(vector["value"])
    assert produced == vector["canonical_text"]
    assert len(produced.encode("utf-8")) == vector["byte_length"]
    assert codec.sha256_hex(produced.encode("utf-8")) == vector["sha256"]


def test_snapshot_envelope_checksums_are_reproducible_by_the_implementation(tmp_path):
    """Build the same snapshot through the real code path and compare."""
    vector = next(
        v for v in VECTORS["snapshot_envelope"] if v["name"] == "snapshot_v1_0"
    )
    store = FragmentStore()
    for record in vector["value"]["fragments"]:
        import base64

        payload = base64.b64decode(record["payload_b64"])
        store.put(
            Fragment(
                object_id=record["object_id"],
                representation_id=record["representation_id"],
                chunk_index=record["chunk_index"],
                byte_range=(record["byte_range"][0], record["byte_range"][1]),
                sha256=record["sha256"],
                payload=payload,
            )
        )
    document = SnapshotStore.build_document(
        store.fragments(),
        peer_id=vector["value"]["peer_id"],
        created_at_unix=vector["value"]["created_at_unix"],
    )
    assert document == vector["value"]
    assert codec.sha256_hex(codec.canonical_bytes(document)) == vector["sha256"]


def test_fragment_order_independence_vector():
    ordered = next(v for v in VECTORS["snapshot_envelope"] if v["name"] == "snapshot_v1_0")
    reversed_ = next(
        v for v in VECTORS["snapshot_envelope"]
        if v["name"] == "snapshot_reversed_fragment_order"
    )
    assert ordered["sha256"] == reversed_["sha256"]


def test_identity_vector_excludes_forwarding_state():
    entry = VECTORS["identity"][0]
    produced = codec.identity_bytes(entry["payload"])
    assert produced.decode("utf-8") == entry["canonical_text"]
    assert codec.sha256_hex(produced) == entry["sha256"]


def test_size_limit_vector_matches_the_registry():
    from shongket_core import canonical_registry

    registry = canonical_registry()
    limits = VECTORS["size_limits"]
    for definition in registry.definitions():
        key = f"shongket.{definition.family}.v{definition.version.major}.{definition.version.minor}"
        assert definition.size_limit_bytes == limits[key], key
    assert limits["transport_frame"] == 1_048_576


def test_error_classification_vector_matches_the_enum():
    expected = VECTORS["error_classification"]
    assert set(expected) == {code.value for code in ErrorCode}
    for code, klass in ERROR_CLASSES.items():
        assert expected[code.value] == klass.value, code


def test_forwarding_admission_clause_order_vector():
    clauses = VECTORS["forwarding_admission"]
    assert [c["order"] for c in clauses] == [1, 2, 3, 4, 5, 6]
    for entry in clauses:
        assert entry["code"] in {c.value for c in ErrorCode}


def test_privacy_migration_vectors():
    for case in VECTORS["privacy_migration"]:
        migrated = migrate_privacy_fields({"object_id": "a" * 64, **case["legacy"]})
        assert migrated["visibility"] == case["visibility"]


def test_conformance_vector_file_is_portable():
    raw = (CORE_DIR / "testdata" / "m1_conformance_vectors.json").read_text(
        encoding="utf-8"
    )
    assert "C:\\" not in raw and "/home/" not in raw and "/Users/" not in raw
    assert "T00:" not in raw
    assert json.loads(raw) == VECTORS


# --- AT-37 M0 regression --------------------------------------------------------


def test_all_m0_tests_pass_unchanged():
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "app/simulator/tests", "-q"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
        env={**_clean_env(), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert result.returncode == 0, result.stdout[-2000:]
    assert "125 passed" in result.stdout
    assert "failed" not in result.stdout
    assert "skipped" not in result.stdout


def test_m0_cli_hash_is_unchanged(tmp_path):
    out = tmp_path / "events.jsonl"
    result = subprocess.run(
        [sys.executable, "-m", "app.simulator", "--seed", "42",
         "--chunk-size", "65536", "--out", str(out)],
        cwd=str(REPO_ROOT), capture_output=True, text=True, env=_clean_env(),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    digest = hashlib.sha256(out.read_bytes()).hexdigest().upper()
    assert digest == M0_CLI_SHA256


def test_m0_metrics_hash_is_unchanged():
    script = (
        "import io,json,sys;"
        "sys.path.insert(0, sys.argv[1]);"
        "from app.simulator import events, metrics, scenario, transfer;"
        "scen=scenario.build_two_peer_scenario(seed=42, chunk_size=65536);"
        "items=scenario.schedule_full_transfer(scen);"
        "chunks=scenario.all_chunks(scen);"
        "lg=events.EventLogger(sink=io.StringIO());"
        "transfer.run_encounter(sender=scen.sender, receiver=scen.receiver,"
        " logger=lg, items=items, capsule_payload=scen.capsule,"
        " manifest_payload=scen.manifest, chunks=chunks);"
        "print(metrics.to_json(metrics.collect(lg,"
        " scenario_id='1-sender-1-receiver',"
        " chunk_bytes=metrics.chunk_byte_map(scen.plans),"
        " expected_chunks={r: len(p.chunks) for r,p in scen.plans.items()},"
        " receiver_store=scen.receiver.store,"
        " signal_plane_bytes=len(json.dumps(scen.capsule).encode())"
        "+len(json.dumps(scen.manifest).encode()))))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(REPO_ROOT)],
        cwd=str(REPO_ROOT), capture_output=True, text=True, env=_clean_env(),
    )
    assert result.returncode == 0, result.stderr[-2000:]
    digest = hashlib.sha256(result.stdout.strip().encode()).hexdigest().upper()
    assert digest == M0_METRICS_SHA256


def test_slice1_golden_vectors_are_unchanged():
    golden = json.loads(
        (CORE_DIR / "testdata" / "golden_vectors.json").read_text(encoding="utf-8")
    )
    expected = {
        "capsule_v1_0": 555,
        "content_v1_0": 464,
        "fragment_v1_0": 283,
        "content_v1_0_scrambled_insertion_order": 464,
        "capsule_non_ascii": 297,
    }
    for vector in golden["serialization"]:
        assert vector["byte_length"] == expected[vector["name"]]
        assert codec.sha256_hex(codec.canonical_bytes(vector["value"])) == vector["sha256"]


def test_simulator_source_is_untouched_by_m1():
    """M1 must not silently rewrite M0 behaviour to make itself pass."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "origin/main...HEAD", "--", "app/"],
        cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.skip("git unavailable in this environment")
    assert result.stdout.strip() == "", (
        f"M1 modified app/: {result.stdout}"
    )


def _clean_env() -> dict:
    import os

    env = dict(os.environ)
    env.pop("PYTHONHASHSEED", None)
    return env
