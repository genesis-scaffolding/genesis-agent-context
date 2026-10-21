"""Manifest model for an agent-context backup archive."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

MANIFEST_SCHEMA_VERSION = 1
"""Current manifest schema version."""

MANIFEST_FILENAME = "MANIFEST.json"
"""Path inside the zip that holds the manifest."""


class Counts(BaseModel):
    """Per-collection item counts captured at export time."""

    journal: int = 0
    profile: int = 0

    model_config = ConfigDict(extra="ignore")


class Manifest(BaseModel):
    """The top-level manifest entry of a backup archive."""

    schema_version: int = Field(..., description="Manifest schema version.")
    generator: str = Field(..., description="Producer tag (e.g. 'agent-context-backup').")
    username: str = Field(..., description="Account the archive belongs to.")
    created_at: datetime = Field(..., description="When the archive was produced (UTC).")
    counts: Counts = Field(default_factory=Counts, description="Per-collection counts.")

    model_config = ConfigDict(extra="ignore")
