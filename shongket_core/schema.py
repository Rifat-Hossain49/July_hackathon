"""Schema registry and version resolution (M1 — AT-23, AT-24).

The registry is the single source of truth for which schema families and
versions this build accepts (``PROTOCOL_SPEC.md`` §9.1).

Design constraints, all from the approved decisions:

* **No global mutable state.** A registry is constructed explicitly and
  is immutable afterwards, so tests cannot leak registrations into each
  other and results cannot depend on import order.
* **Order independence.** Building the same definitions in any order
  yields an equal registry and identical resolutions.
* **No inference.** A higher minor is accepted only when its
  compatibility is explicitly registered. There is no "probably fine"
  path.
* **No discovery.** No plugin scanning, dynamic import or network fetch.

Minor-version policy (D-M1-05, as ratified)
-------------------------------------------
For a known family and major, with ``exact`` = the minor of the
registered definition:

=====================  ========================================
Declared minor         Outcome
=====================  ========================================
``== exact``           accepted — the exact registered version
``!= exact``           accepted **only** if explicitly registered,
                       whether numerically lower or higher
unknown major          ``VERSION_UNSUPPORTED``
unknown family         ``SCHEMA_INVALID``
=====================  ========================================

**Ordering grants nothing.** An earlier draft accepted any lower minor
automatically, on the reasoning that an older sender is one we already
understand. That reasoning does not hold: a receiver holds no record of
what an unregistered earlier release actually looked like, so treating
"lower" as "safe" is inference — exactly what D-M1-05 forbids. Both
directions now require an explicit entry.

A compatibility entry for the exact registered minor is refused at
construction, because that version is already accepted and the entry
would be dead configuration.

The unknown-family case is ``SCHEMA_INVALID`` rather than
``VERSION_UNSUPPORTED`` because the failure is not about a version: the
identifier names an object this protocol does not define at any version.
AT-24 fixes the code only for version failures, so this distinction is a
Slice-1 implementation choice and is recorded as such in the report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping

from .errors import ErrorCode, ProtocolError
from .version import SchemaId, SchemaVersion, parse_schema_id


@dataclass(frozen=True)
class SchemaDefinition:
    """One registered schema family at one major version.

    ``required_fields`` records the fields the canonical schema declares
    as mandatory; ``optional_fields`` those it declares but does not
    require. Together they are the schema's *known* fields — anything
    else in a payload is an unknown field for AT-23 purposes.

    Slice 1 checks required-field presence only; full type, enum and
    size validation stays with the existing M0 boundary until Slice 4,
    so this slice does not duplicate or weaken it.
    """

    family: str
    version: SchemaVersion
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()

    @property
    def key(self) -> tuple[str, int]:
        return (self.family, self.version.major)

    @property
    def known_fields(self) -> frozenset[str]:
        return frozenset(self.required_fields) | frozenset(self.optional_fields)


@dataclass(frozen=True)
class MinorCompatibility:
    """An explicit statement that one higher minor is understood."""

    family: str
    major: int
    minor: int

    @property
    def key(self) -> tuple[str, int, int]:
        return (self.family, self.major, self.minor)


@dataclass(frozen=True)
class Resolution:
    """The outcome of resolving a schema identifier."""

    schema_id: SchemaId
    definition: SchemaDefinition
    #: True when the identifier used the legacy ``...v<major>`` form.
    legacy_alias: bool
    #: True when acceptance came from an explicit compatibility entry.
    via_registered_compatibility: bool

    @property
    def family(self) -> str:
        return self.schema_id.family

    @property
    def version(self) -> SchemaVersion:
        return self.schema_id.version


@dataclass(frozen=True)
class AcceptedPayload:
    """A payload accepted by the registry, with unknown fields recorded."""

    resolution: Resolution
    payload: Mapping[str, object]
    #: Fields present in the payload but not declared by the schema.
    #: Ignored, never persisted, never echoed back (AT-23).
    ignored_fields: tuple[str, ...] = field(default=())


class SchemaRegistry:
    """Immutable registry of known schema families and versions."""

    def __init__(
        self,
        definitions: Iterable[SchemaDefinition],
        compatibilities: Iterable[MinorCompatibility] = (),
    ) -> None:
        by_key: dict[tuple[str, int], SchemaDefinition] = {}
        for definition in definitions:
            existing = by_key.get(definition.key)
            if existing is not None:
                if existing == definition:
                    raise ValueError(
                        f"duplicate registration for {definition.family} "
                        f"major {definition.version.major}"
                    )
                raise ValueError(
                    f"contradictory registration for {definition.family} "
                    f"major {definition.version.major}: "
                    f"{existing!r} vs {definition!r}"
                )
            by_key[definition.key] = definition

        compat: set[tuple[str, int, int]] = set()
        for entry in compatibilities:
            if (entry.family, entry.major) not in by_key:
                raise ValueError(
                    f"compatibility for unregistered schema "
                    f"{entry.family} major {entry.major}"
                )
            exact = by_key[(entry.family, entry.major)].version.minor
            if entry.minor == exact:
                raise ValueError(
                    f"compatibility entry {entry.family} "
                    f"v{entry.major}.{entry.minor} equals the exact "
                    "registered version, which is already accepted; the "
                    "entry would have no effect"
                )
            if entry.key in compat:
                raise ValueError(f"duplicate compatibility entry {entry.key!r}")
            compat.add(entry.key)

        self._definitions = by_key
        self._compatibilities = frozenset(compat)

    # -- introspection ------------------------------------------------------

    @property
    def families(self) -> tuple[str, ...]:
        return tuple(sorted({family for family, _major in self._definitions}))

    def definitions(self) -> tuple[SchemaDefinition, ...]:
        """Registered definitions in a deterministic order."""
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    def registered_compatibilities(self) -> tuple[MinorCompatibility, ...]:
        return tuple(
            MinorCompatibility(family, major, minor)
            for family, major, minor in sorted(self._compatibilities)
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SchemaRegistry):
            return NotImplemented
        return (
            self._definitions == other._definitions
            and self._compatibilities == other._compatibilities
        )

    def __hash__(self) -> int:
        return hash((tuple(sorted(self._definitions)), self._compatibilities))

    # -- resolution ---------------------------------------------------------

    def resolve(self, identifier: object) -> Resolution:
        """Resolve a schema identifier to its registered definition.

        Raises
        ------
        ProtocolError
            ``SCHEMA_INVALID`` when the identifier is absent, not a
            string, or names an unknown family.
            ``VERSION_UNSUPPORTED`` when the version syntax is malformed,
            the major is unknown, or the minor is above the baseline
            without a registered compatibility entry.
        """
        schema_id = parse_schema_id(identifier)

        known_families = {family for family, _major in self._definitions}
        if schema_id.family not in known_families:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"unknown schema family {schema_id.family!r}",
            )

        definition = self._definitions.get(schema_id.family_major_key())
        if definition is None:
            raise ProtocolError(
                ErrorCode.VERSION_UNSUPPORTED,
                f"unsupported major version {schema_id.major} for "
                f"{schema_id.family!r}",
            )

        exact_minor = definition.version.minor
        via_compat = False
        if schema_id.minor != exact_minor:
            # Non-exact in either direction. Numeric ordering grants
            # nothing: a lower minor is no more "obviously safe" than a
            # higher one, because the receiver has no record of what that
            # release actually looked like.
            if schema_id.to_compat_key() not in self._compatibilities:
                raise ProtocolError(
                    ErrorCode.VERSION_UNSUPPORTED,
                    f"minor version {schema_id.minor} of {schema_id.family!r} "
                    f"v{schema_id.major} is not registered as compatible "
                    f"(exact registered minor is {exact_minor}); "
                    "compatibility is never inferred from ordering",
                )
            via_compat = True

        return Resolution(
            schema_id=schema_id,
            definition=definition,
            legacy_alias=schema_id.legacy_alias,
            via_registered_compatibility=via_compat,
        )

    def accept(self, payload: Mapping[str, object]) -> AcceptedPayload:
        """Resolve ``payload['schema']`` and check its declared fields.

        Version resolution happens **before** any structural inspection,
        so an unsupported version is reported as ``VERSION_UNSUPPORTED``
        even when the payload is also malformed (AT-24 case b).

        Unknown fields are recorded and ignored, never treated as errors
        and never echoed back (AT-23).
        """
        if not isinstance(payload, Mapping):
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"payload must be an object, got {type(payload).__name__}",
            )

        resolution = self.resolve(payload.get("schema"))

        definition = resolution.definition
        missing = sorted(
            f for f in definition.required_fields if f not in payload
        )
        if missing:
            raise ProtocolError(
                ErrorCode.SCHEMA_INVALID,
                f"missing required field(s) {missing!r} for "
                f"{resolution.family!r}",
            )

        known = definition.known_fields
        ignored = tuple(sorted(k for k in payload if k not in known))
        return AcceptedPayload(
            resolution=resolution, payload=payload, ignored_fields=ignored
        )
