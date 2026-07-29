"""Shared pytest fixtures for the Shongket M0 acceptance-test slice.

The fixtures reuse the deterministic ``build_two_peer_scenario`` builder
so tests do not duplicate fixture shape. Two simulated peers are
exposed: ``scenario.sender`` and ``scenario.receiver``.
"""

from __future__ import annotations

import io

import pytest

from app.simulator import events, scenario, transfer


@pytest.fixture()
def deterministic_scenario():
    """The canonical two-peer scenario used by every acceptance test."""
    return scenario.build_two_peer_scenario()


@pytest.fixture()
def capsule_logger():
    """Fresh in-memory event logger for tests."""
    return events.EventLogger(sink=io.StringIO())


@pytest.fixture()
def full_transfer_result(deterministic_scenario, capsule_logger):
    """Run a full deterministic encounter against the canonical scenario.

    Returns ``(scenario, logger, result)`` so tests can assert on both
    the event log and the ``EncounterResult`` summary.
    """
    items = scenario.schedule_full_transfer(deterministic_scenario)
    chunks = scenario.all_chunks(deterministic_scenario)
    result = transfer.run_encounter(
        sender=deterministic_scenario.sender,
        receiver=deterministic_scenario.receiver,
        logger=capsule_logger,
        items=items,
        capsule_payload=deterministic_scenario.capsule,
        manifest_payload=deterministic_scenario.manifest,
        chunks=chunks,
    )
    return deterministic_scenario, capsule_logger, result