"""Seed a new account's profile documents.

Called once, from :func:`agent_context.users.create_user`, at the
moment an account comes into existence. Writes the packaged
defaults through :class:`agent_context.profile.ProfileFacade` so the
first write goes down the normal snapshot path: the seed shows up
as version 1 in history and an operator can roll back to it like any
other write.

Two invariants:

- **Never clobber.** A target whose canonical file already exists is
  skipped. A re-created account (delete + create, Radicale keeps the
  old collection tree on disk) and a future per-user seed both land
  here, and neither should lose edits.
- **Never raise into account creation.** The account exists once the
  users table and the htpasswd are written. A profile root the
  process cannot write leaves an account with empty documents, which
  is recoverable by hand; a signup that raises after the account was
  created is not. Failures come back as :attr:`SeedResult.errors` for
  the caller to surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..configs import Configs, config_path_for
from ..profile import TARGETS, ProfileFacade, ProfileTarget, resolve_location
from .documents import seed_document

SEED_NOTE = "seed: default document written at account creation"
"""Snapshot note recorded with the seeded write."""


@dataclass(frozen=True)
class SeedResult:
    """Outcome of :func:`seed_new_account`."""

    profile_root: Path
    written: tuple[ProfileTarget, ...] = ()
    skipped: tuple[ProfileTarget, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when no target failed to seed."""
        return not self.errors


def profile_root_for(username: str) -> Path:
    """Resolve the per-user profile root for ``username``.

    Built from a :class:`agent_context.configs.Configs` so the seed
    lands exactly where the app will read it, including any path the
    user's own ``configs.yaml`` overrides. Reads config only; creates
    nothing.
    """
    return Path(Configs(yaml_path=config_path_for(username)).paths.profile_root)


def seed_new_account(
    username: str,
    *,
    documents: dict[ProfileTarget, str] | None = None,
) -> SeedResult:
    """Write the default profile documents for a brand new ``username``.

    Args:
        username: The account being created. Resolves the profile root.
        documents: Optional per-target content overrides. A target
            missing from the mapping falls back to the packaged seed.

    Returns:
        A :class:`SeedResult` naming what was written, what was left
        alone because it already existed, and any per-target errors.
    """
    overrides = documents or {}
    root = profile_root_for(username)
    facade = ProfileFacade(root)
    written: list[ProfileTarget] = []
    skipped: list[ProfileTarget] = []
    errors: list[str] = []

    for target in TARGETS:
        if resolve_location(target, root).path.exists():
            skipped.append(target)
            continue
        content = overrides.get(target)
        if content is None:
            content = seed_document(target)
        try:
            result = facade.write(target, content, note=SEED_NOTE)
        except OSError as e:
            errors.append(f"{target.value}: {e}")
            continue
        if result.ok:
            written.append(target)
        else:
            errors.append(f"{target.value}: {result.error}")

    return SeedResult(
        profile_root=root,
        written=tuple(written),
        skipped=tuple(skipped),
        errors=tuple(errors),
    )


__all__ = [
    "SEED_NOTE",
    "SeedResult",
    "profile_root_for",
    "seed_new_account",
]