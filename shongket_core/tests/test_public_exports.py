"""Public package surface (M1 Slice 1).

Guards the contract that every name in ``shongket_core.__all__`` is
reachable after a plain ``import shongket_core``. An earlier revision
listed ``codec`` in ``__all__`` without importing the submodule, so
``shongket_core.codec`` raised ``AttributeError`` while
``from shongket_core import codec`` worked — an inconsistent surface
depending on which import form the caller happened to use.

Also asserts that importing the package has no side effects and creates
no shared mutable state.
"""

from __future__ import annotations

import importlib
import io
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import shongket_core


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_every_all_entry_is_reachable_after_plain_import():
    missing = [name for name in shongket_core.__all__ if not hasattr(shongket_core, name)]
    assert missing == []


def test_codec_is_reachable_by_attribute_and_by_from_import():
    assert shongket_core.codec.canonical_text({"a": 1}) == '{"a":1}'

    from shongket_core import codec as from_import

    assert from_import is shongket_core.codec


def test_plain_import_in_a_fresh_process_exposes_codec():
    """The failing path before the fix: attribute access after import."""
    script = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import shongket_core;"
        "print(shongket_core.codec.canonical_text({'a': 1}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script, str(REPO_ROOT)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == '{"a":1}'


def test_import_has_no_side_effects():
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        importlib.reload(shongket_core)
    assert buffer.getvalue() == ""


def test_canonical_registry_returns_independent_instances():
    first = shongket_core.canonical_registry()
    second = shongket_core.canonical_registry()
    assert first == second
    assert first is not second
