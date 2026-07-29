"""Shongket M0 deterministic simulator slice.

Implements only the Milestone 0 vertical slice described in the approved
plan: synthetic source media, manually supplied semantic capsule, fixed-size
SHA-256 chunking, two simulated peers, capsule-before-media scheduling, and
structured event logging. Excludes Android transport, real radio, offline AI,
production crypto identity, and any coded (Reed-Solomon / fountain / RaptorQ)
reconstruction.
"""

__all__ = [
    "media",
    "capsule",
    "manifest",
    "validation",
    "chunks",
    "hashutil",
    "priority",
    "store",
    "events",
    "peer",
    "transfer",
    "ingress",
    "scenario",
    "gate",
    "persistence",
    "main",
]
