"""Protocol version parsing (M1 — D-M1-05).

Implements the identifier format frozen in ``PROTOCOL_SPEC.md`` §9.1:

```
shongket.<family>.v<MAJOR>.<MINOR>
```

with the bare ``shongket.<family>.v<MAJOR>`` form accepted **only** as
the documented legacy alias for ``<MAJOR>.0``.

Design notes
------------
Parsing is deliberately strict. Every rejection below exists because the
alternative would be a silent coercion, which D-M1-05 forbids:

* leading zeros (``v01``) are rejected — otherwise ``v01`` and ``v1``
  would be two spellings of one version, and a version string that has
  two spellings cannot be part of byte-stable serialization;
* surrounding whitespace is rejected rather than stripped, including a
  trailing newline or CRLF;
* more than two numeric components is rejected, not truncated;
* a missing minor becomes ``0`` **only** through the documented legacy
  alias, never through inference about intent.

Nothing here consults a clock, a random source, or any mutable global.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import ErrorCode, ProtocolError


PREFIX = "shongket"

# family: lowercase, starts with a letter. major/minor: no leading zeros.
#
# Matched with re.fullmatch and no anchors. Using ``$`` here would be a
# bug: in Python ``$`` also matches immediately before a trailing
# newline, so "shongket.content.v1.0\n" would parse as a valid
# identifier. Two byte strings mapping to one schema identity breaks the
# one-spelling-per-version property that byte-stable serialization
# depends on. ``fullmatch`` has no such exception.
_IDENTIFIER = re.compile(
    r"shongket\.([a-z][a-z0-9_]*)\.v(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?"
)


@dataclass(frozen=True, order=True)
class SchemaVersion:
    """A ``<major>.<minor>`` protocol version."""

    major: int
    minor: int

    def __post_init__(self) -> None:
        if self.major < 0 or self.minor < 0:
            raise ValueError("version components must be non-negative")

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}"


@dataclass(frozen=True)
class SchemaId:
    """A parsed canonical schema identifier."""

    family: str
    version: SchemaVersion
    #: True when parsed from the legacy ``...v<major>`` form.
    legacy_alias: bool = False

    @property
    def major(self) -> int:
        return self.version.major

    @property
    def minor(self) -> int:
        return self.version.minor

    def canonical(self) -> str:
        """The canonical identifier, always in explicit major.minor form."""
        return f"{PREFIX}.{self.family}.v{self.version.major}.{self.version.minor}"

    def legacy(self) -> str:
        """The legacy alias form. Only ever means ``<major>.0``."""
        return f"{PREFIX}.{self.family}.v{self.version.major}"

    def family_major_key(self) -> tuple[str, int]:
        """Registry lookup key: ``(family, major)``."""
        return (self.family, self.version.major)

    def to_compat_key(self) -> tuple[str, int, int]:
        """Compatibility lookup key: ``(family, major, minor)``."""
        return (self.family, self.version.major, self.version.minor)

    def __str__(self) -> str:
        return self.canonical()


def parse_schema_id(identifier: object) -> SchemaId:
    """Parse a canonical or legacy schema identifier.

    Raises
    ------
    ProtocolError
        ``SCHEMA_INVALID`` when ``identifier`` is absent or not a string
        — the payload cannot be identified at all, which is a structural
        problem rather than a version one.
        ``VERSION_UNSUPPORTED`` when the string is present but its
        version syntax is not one this protocol defines. Refusing here
        keeps the §9.1 guarantee that a version is resolved before any
        structural parsing is attempted.
    """
    if not isinstance(identifier, str):
        raise ProtocolError(
            ErrorCode.SCHEMA_INVALID,
            f"schema identifier must be a string, got "
            f"{type(identifier).__name__}",
        )

    match = _IDENTIFIER.fullmatch(identifier)
    if match is None:
        raise ProtocolError(
            ErrorCode.VERSION_UNSUPPORTED,
            f"malformed schema identifier {identifier!r}; expected "
            f"{PREFIX}.<family>.v<major>[.<minor>]",
        )

    family, major_text, minor_text = match.group(1), match.group(2), match.group(3)
    legacy = minor_text is None
    minor = 0 if legacy else int(minor_text)
    return SchemaId(
        family=family,
        version=SchemaVersion(major=int(major_text), minor=minor),
        legacy_alias=legacy,
    )
