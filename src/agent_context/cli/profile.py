"""CLI: the profile store (persona and agent operating protocol).

Command surface::

    gac profile list
    gac profile read <target>
    gac profile write <target> --content TEXT | --content-file PATH | --stdin
    gac profile edit <target> --old TEXT --new TEXT [--global-replace]
    gac profile history <target> [--limit N]
    gac profile restore <target> --version TS [--note TEXT]

    gac protocol read
    gac protocol write --content TEXT | --content-file PATH | --stdin
    gac protocol edit --old TEXT --new TEXT [--global-replace]
    gac protocol history [--limit N]
    gac protocol restore --version TS [--note TEXT]

``<target>`` is ``profile`` (the persona) or ``protocol`` (the agent
operating protocol). The ``gac profile`` group is the generic store
interface; the ``gac protocol`` group is the same operations pinned to
the operating protocol, so the protocol is reachable by its own name
from the command line, exactly like it has its own page in the UI and
its own routes under ``/protocol`` in the API.

The commands talk to the local store through the
:class:`agent_context.core.facade.Facade`, the same way the journal
commands do. They never talk to the HTTP API.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

from ..configs import DEFAULT_USER, resolve_config_path
from ..core.facade import Facade
from ..profile import ProfileTarget, parse_target

profile_app = typer.Typer(help="Manage the profile store (persona and operating protocol).")
protocol_app = typer.Typer(help="Manage the agent operating protocol.")

TargetArg = Annotated[str, typer.Argument(help="Target: profile or protocol.")]
UserOpt = Annotated[
    str,
    typer.Option("--user", "-u", help=f"User name. Defaults to '{DEFAULT_USER}'. Determines config location."),
]
ContentOpt = Annotated[str | None, typer.Option("--content", "-c", help="New content as a literal string.")]
FileOpt = Annotated[
    Path | None,
    typer.Option("--content-file", "--file", "-f", help="Read the new content from this file ('-' for stdin)."),
]
StdinOpt = Annotated[bool, typer.Option("--stdin", help="Read the new content from stdin.")]
NoteOpt = Annotated[str | None, typer.Option("--note", help="Snapshot note describing the change.")]
OldOpt = Annotated[str, typer.Option("--old", help="Text to replace.")]
NewOpt = Annotated[str, typer.Option("--new", help="Replacement text.")]
GlobalOpt = Annotated[
    bool,
    typer.Option("--global-replace", "--global", help="Replace every occurrence, not just the first."),
]
LimitOpt = Annotated[int | None, typer.Option("--limit", "-n", help="Max snapshots to list.")]
VersionOpt = Annotated[
    str,
    typer.Option("--version", "-v", help="Snapshot ts, unique prefix, or filename."),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _facade(user: str) -> Facade:
    """Build a per-user facade for CLI use."""
    return Facade(resolve_config_path(user), ensure_server=False)


def _resolve_target(value: str) -> ProfileTarget:
    """Parse a target string, exiting with a clear message when invalid."""
    try:
        return parse_target(value)
    except ValueError as e:
        typer.echo(f"error: {e}", err=True)
        raise typer.Exit(code=1) from None


def _read_content(
    *,
    content: str | None,
    file: Path | None,
    stdin: bool,
) -> str:
    """Pick the content source for a write.

    Exactly one of ``content`` / ``file`` / ``stdin`` must be given.
    """
    provided = (content is not None, file is not None, stdin)
    if sum(provided) != 1:
        typer.echo("error: give exactly one of --content, --content-file, --stdin", err=True)
        raise typer.Exit(code=1)
    if content is not None:
        return content
    if file is not None:
        if str(file) == "-":
            return sys.stdin.read()
        try:
            return file.read_text(encoding="utf-8")
        except OSError as e:
            typer.echo(f"error: cannot read {file}: {e}", err=True)
            raise typer.Exit(code=1) from None
    return sys.stdin.read()


def _list(facade: Facade) -> None:
    """Print every target with its path, existence, and size."""
    listed = facade.profile.list()
    typer.echo(f"{'TARGET':<10} {'EXISTS':<7} {'BYTES':>8}  PATH")
    for row in listed.rows:
        exists = "yes" if row.exists else "no"
        typer.echo(f"{row.target.value:<10} {exists:<7} {row.bytes:>8}  {row.path}")


def _read(facade: Facade, target: ProfileTarget) -> None:
    """Print the canonical content for ``target``."""
    result = facade.profile.read(target)
    if not result.ok:
        typer.echo(f"error: {result.error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(result.content)


def _write(facade: Facade, target: ProfileTarget, content: str, note: str | None) -> None:
    """Overwrite the canonical file for ``target``."""
    result = facade.profile.write(target, content, note=note)
    if not result.ok:
        typer.echo(f"error: {result.error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"wrote {result.bytes_written} bytes to {result.path}")
    if result.snapshot is not None and result.snapshot.ok:
        typer.echo(f"snapshot {result.snapshot.filename}")
    else:
        typer.echo("no snapshot (content unchanged)")


def _edit(
    facade: Facade,
    target: ProfileTarget,
    old_text: str,
    new_text: str,
    global_replace: bool,
    note: str | None,
) -> None:
    """Replace ``old_text`` with ``new_text`` in the canonical file."""
    result = facade.profile.edit(
        target,
        old_text,
        new_text,
        global_replace=global_replace,
        note=note,
    )
    if not result.ok:
        typer.echo(f"error: {result.error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"replaced {result.replacements} occurrence(s) in {result.path}")
    if result.snapshot is not None and result.snapshot.ok:
        typer.echo(f"snapshot {result.snapshot.filename}")
    else:
        typer.echo("no snapshot (content unchanged)")


def _history(facade: Facade, target: ProfileTarget, limit: int | None) -> None:
    """Print the snapshots for ``target`` (newest first)."""
    result = facade.profile.history(target, limit=limit)
    if not result.ok:
        typer.echo(f"error: {result.error}", err=True)
        raise typer.Exit(code=1)
    if not result.snapshots:
        typer.echo("(no snapshots)")
        return
    typer.echo(f"{'TS':<26} {'SIZE':>8}  COMMAND  NOTE")
    for row in result.snapshots:
        command = row.meta.command if row.meta is not None else "?"
        note = row.meta.note if row.meta is not None else ""
        typer.echo(f"{row.ts:<26} {row.size:>8}  {command:<8} {note or ''}".rstrip())
    typer.echo(f"total {result.total}")


def _restore(facade: Facade, target: ProfileTarget, version: str, note: str | None) -> None:
    """Restore ``target`` from a snapshot."""
    result = facade.profile.restore(target, version, note=note)
    if not result.ok:
        typer.echo(f"error: {result.error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"restored {result.applied_filename} ({result.applied_size} bytes)")
    if result.pre_restore_snapshot is not None:
        typer.echo(f"pre-restore snapshot {result.pre_restore_snapshot.filename}")


# ---------------------------------------------------------------------------
# gac profile ...
# ---------------------------------------------------------------------------


@profile_app.command(name="list")
def profile_list(user: UserOpt = DEFAULT_USER) -> None:
    """List the profile targets with their path, existence, and size."""
    facade = _facade(user)
    try:
        _list(facade)
    finally:
        facade.shutdown()


@profile_app.command(name="read")
def profile_read(target: TargetArg, user: UserOpt = DEFAULT_USER) -> None:
    """Print the canonical content for a target."""
    parsed = _resolve_target(target)
    facade = _facade(user)
    try:
        _read(facade, parsed)
    finally:
        facade.shutdown()


@profile_app.command(name="write")
def profile_write(
    target: TargetArg,
    content: ContentOpt = None,
    file: FileOpt = None,
    stdin: StdinOpt = False,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Overwrite a target's canonical file."""
    parsed = _resolve_target(target)
    body = _read_content(content=content, file=file, stdin=stdin)
    facade = _facade(user)
    try:
        _write(facade, parsed, body, note)
    finally:
        facade.shutdown()


@profile_app.command(name="edit")
def profile_edit(
    target: TargetArg,
    old_text: OldOpt,
    new_text: NewOpt,
    global_replace: GlobalOpt = False,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Replace text inside a target's canonical file."""
    parsed = _resolve_target(target)
    facade = _facade(user)
    try:
        _edit(facade, parsed, old_text, new_text, global_replace, note)
    finally:
        facade.shutdown()


@profile_app.command(name="history")
def profile_history(
    target: TargetArg,
    limit: LimitOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """List the snapshots of a target (newest first)."""
    parsed = _resolve_target(target)
    facade = _facade(user)
    try:
        _history(facade, parsed, limit)
    finally:
        facade.shutdown()


@profile_app.command(name="restore")
def profile_restore(
    target: TargetArg,
    version: VersionOpt,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Restore a target from a snapshot."""
    parsed = _resolve_target(target)
    facade = _facade(user)
    try:
        _restore(facade, parsed, version, note)
    finally:
        facade.shutdown()


# ---------------------------------------------------------------------------
# gac protocol ...
# ---------------------------------------------------------------------------


@protocol_app.command(name="read")
def protocol_read(user: UserOpt = DEFAULT_USER) -> None:
    """Print the agent operating protocol."""
    facade = _facade(user)
    try:
        _read(facade, ProfileTarget.PROTOCOL)
    finally:
        facade.shutdown()


@protocol_app.command(name="write")
def protocol_write(
    content: ContentOpt = None,
    file: FileOpt = None,
    stdin: StdinOpt = False,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Overwrite the agent operating protocol."""
    body = _read_content(content=content, file=file, stdin=stdin)
    facade = _facade(user)
    try:
        _write(facade, ProfileTarget.PROTOCOL, body, note)
    finally:
        facade.shutdown()


@protocol_app.command(name="edit")
def protocol_edit(
    old_text: OldOpt,
    new_text: NewOpt,
    global_replace: GlobalOpt = False,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Replace text inside the agent operating protocol."""
    facade = _facade(user)
    try:
        _edit(facade, ProfileTarget.PROTOCOL, old_text, new_text, global_replace, note)
    finally:
        facade.shutdown()


@protocol_app.command(name="history")
def protocol_history(limit: LimitOpt = None, user: UserOpt = DEFAULT_USER) -> None:
    """List the snapshots of the agent operating protocol (newest first)."""
    facade = _facade(user)
    try:
        _history(facade, ProfileTarget.PROTOCOL, limit)
    finally:
        facade.shutdown()


@protocol_app.command(name="restore")
def protocol_restore(
    version: VersionOpt,
    note: NoteOpt = None,
    user: UserOpt = DEFAULT_USER,
) -> None:
    """Restore the agent operating protocol from a snapshot."""
    facade = _facade(user)
    try:
        _restore(facade, ProfileTarget.PROTOCOL, version, note)
    finally:
        facade.shutdown()


__all__ = ["profile_app", "protocol_app"]
