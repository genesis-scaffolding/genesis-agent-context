"""Packaged default profile documents.

The two markdown files next to this module are the baseline a new
account starts with. One file per profile target, named after the
target so the mapping to :data:`agent_context.profile.TARGETS` is
one-to-one and obvious.

They are documents, not code: they are read verbatim and written
into a new user's profile root at account creation (see
:mod:`agent_context.seed.facade`).
"""

from __future__ import annotations

from pathlib import Path

from ..profile import TARGET_FILENAME, ProfileTarget

SEED_DIR = Path(__file__).resolve().parent
"""Directory holding the packaged seed documents."""

SEED_FILENAME: dict[ProfileTarget, str] = dict(TARGET_FILENAME)
"""Seed filename per target. Same names as the canonical files they
become, so a seed file and its destination read the same way."""


def seed_document(target: ProfileTarget) -> str:
    """Return the packaged seed markdown for ``target``.

    Raises :class:`KeyError` for an unknown target and
    :class:`OSError` when the packaged file is missing (a broken
    install, which must be loud).
    """
    return (SEED_DIR / SEED_FILENAME[target]).read_text(encoding="utf-8")


__all__ = [
    "SEED_DIR",
    "SEED_FILENAME",
    "seed_document",
]