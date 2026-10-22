"""Default profile documents written when an account is created.

New accounts start with a usable persona (``profile``) and operating
protocol (``protocol``) instead of empty files, so an agent serving a
fresh account has something to work from on day one.

The seed is applied once, at account creation
(:func:`agent_context.users.create_user`), never on login. Existing
documents are never overwritten. ADR-036.
"""

from .documents import SEED_DIR, SEED_FILENAME, seed_document
from .facade import SEED_NOTE, SeedResult, profile_root_for, seed_new_account

__all__ = [
    "SEED_DIR",
    "SEED_FILENAME",
    "SEED_NOTE",
    "SeedResult",
    "profile_root_for",
    "seed_document",
    "seed_new_account",
]