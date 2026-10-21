"""Facade for the application.

The Facade provides a single entry point to the core library.
Each instance represents an independent application context with its own
configuration. Multiple instances can coexist (e.g., multi-user scenarios).

Usage:
    facade = Facade()                          # uses default XDG path
    facade = Facade("/path/to/configs.yaml")   # explicit yaml path

    print(facade.configs.app_name)
    facade.journal.get_entry(today)
    facade.profile.read(ProfileTarget.PROFILE)

    with Facade() as facade:
        facade.profile.write(...)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..configs import Configs

if TYPE_CHECKING:
    from ..backup.facade import BackupFacade
    from ..journal.facade import JournalFacade
    from ..profile.facade import ProfileFacade


class Facade:
    """Single entry point to the application core.

    Args:
        yaml_path: Optional path to a configs.yaml file.
                   If None, uses the default XDG path. If that default
                   file does not exist, uses internal defaults only.
                   If provided but not found, raises FileNotFoundError.
        ensure_server: Ignored in agent-context (no Radicale server).
    """

    def __init__(
        self,
        yaml_path: str | Path | None = None,
        *,
        ensure_server: bool = True,
    ) -> None:
        self._configs = Configs(yaml_path=yaml_path)
        self._journal: JournalFacade | None = None
        self._backup: BackupFacade | None = None
        self._profile: ProfileFacade | None = None

    @property
    def configs(self) -> Configs:
        """Return the configuration object."""
        return self._configs

    @property
    def journal(self) -> JournalFacade:
        """Return the Journal facade for markdown entries.

        Journal entries live under ``<journal_root>/<user>/``.
        """
        if self._journal is None:
            from ..journal.facade import JournalFacade

            cfg = self.configs
            self._journal = JournalFacade(cfg.paths.journal_root / cfg.user)
        return self._journal

    @property
    def profile(self) -> ProfileFacade:
        """Return the Profile facade for profile and life-story storage."""
        if self._profile is None:
            from ..profile.facade import ProfileFacade

            self._profile = ProfileFacade(self._configs.paths.profile_root)
        return self._profile

    @property
    def backup(self) -> BackupFacade:
        """Return the Backup facade for export and restore."""
        if self._backup is None:
            from ..backup.facade import BackupFacade

            self._backup = BackupFacade(self)
        return self._backup

    def shutdown(self) -> None:
        """No-op placeholder for API compatibility."""
        pass

    def restart_server(self) -> None:
        """No-op placeholder for API compatibility (no Radicale in agent-context)."""
        pass

    def __enter__(self) -> Facade:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.shutdown()
