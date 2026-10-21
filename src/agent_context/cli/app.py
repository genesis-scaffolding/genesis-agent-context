"""CLI application using Typer."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import typer

from ..configs import CONFIG_PATH_ENV, DEFAULT_USER, resolve_config_path
from ..core.facade import Facade
from .user import user_app

app = typer.Typer(help="CLI for agent-context (persona, memory, and handover stores).")
app.add_typer(user_app, name="user")

_user_option = typer.Option(
    DEFAULT_USER,
    "--user",
    "-u",
    help=f"User name. Defaults to '{DEFAULT_USER}'. Determines config location.",
)


@app.command()
def info(
    user: str = _user_option,
) -> None:
    """Print main configuration values."""
    config_path = resolve_config_path(user)
    facade = Facade(config_path)
    cfg = facade.configs

    typer.echo(f"user         : {cfg.user}")
    typer.echo(f"app_name     : {cfg.app_name}")
    typer.echo(f"paths.config : {cfg.paths.config}")
    typer.echo(f"paths.data    : {cfg.paths.data}")
    typer.echo(f"paths.state   : {cfg.paths.state}")
    typer.echo(f"paths.cache   : {cfg.paths.cache}")
    facade.shutdown()


# ---------------------------------------------------------------------------
# Journals
# ---------------------------------------------------------------------------

journals_app = typer.Typer(help="Manage journal entries (memory and handover).")
app.add_typer(journals_app, name="journals")


@journals_app.command(name="list")
def journal_list(
    user: str = _user_option,
    type_filter: str | None = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by entry type (e.g. memory, memory-synthesis, daily-handover).",
    ),
    limit: int = typer.Option(50, "--limit", "-n", help="Max entries to return."),
) -> None:
    """List journal entries."""
    config_path = resolve_config_path(user)
    facade = Facade(config_path, ensure_server=False)
    try:
        entries = facade.journal.list_entries()
        if type_filter:
            entries = [e for e in entries if e.type and e.type.value == type_filter]
        entries = entries[:limit]
        if not entries:
            typer.echo("(no entries)")
            return
        for e in entries:
            label = e.date.isoformat()
            if e.reference_date:
                label = f"{e.reference_date.isoformat()} ({e.date.isoformat()})"
            title = e.title or "(no title)"
            type_str = f"[{e.type.value}]" if e.type else ""
            typer.echo(f"{e.uid[:8]}  {label}  {type_str}  {title}")
    finally:
        facade.shutdown()


@journals_app.command(name="read")
def journal_read(
    uid: str = typer.Argument(..., help="Entry UID."),
    user: str = _user_option,
) -> None:
    """Read a journal entry by UID."""
    config_path = resolve_config_path(user)
    facade = Facade(config_path, ensure_server=False)
    try:
        entry = facade.journal.get_entry(uid)
        if entry is None:
            typer.echo(f"Entry '{uid}' not found.", err=True)
            raise typer.Exit(code=1)
        typer.echo(f"# {entry.title or '(no title)'}")
        typer.echo(f"Date: {entry.date.isoformat()}")
        if entry.reference_date:
            typer.echo(f"Reference date: {entry.reference_date.isoformat()}")
        if entry.type:
            typer.echo(f"Type: {entry.type.value}")
        typer.echo()
        typer.echo(entry.content)
    finally:
        facade.shutdown()


@journals_app.command(name="create")
def journal_create(
    content: str = typer.Argument(..., help="Entry content (markdown)."),
    type_value: str = typer.Option("daily", "--type", "-t", help="Entry type (daily, memory, handover, etc.)."),
    date_value: str | None = typer.Option(None, "--date", "-d", help="Entry date (YYYY-MM-DD). Defaults to today."),
    title: str | None = typer.Option(None, "--title", help="Entry title."),
    user: str = _user_option,
) -> None:
    """Create a new journal entry."""
    from ..journal.facade import Entry, EntryType

    entry_date = date.fromisoformat(date_value) if date_value else date.today()
    entry_type = EntryType(type_value) if type_value else None
    entry = Entry(
        date=entry_date,
        title=title,
        type=entry_type,
        content=content,
    )
    config_path = resolve_config_path(user)
    facade = Facade(config_path, ensure_server=False)
    try:
        facade.journal.save_entry(entry)
        typer.echo(f"Created entry: {entry.uid}")
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    finally:
        facade.shutdown()


@journals_app.command(name="delete")
def journal_delete(
    uid: str = typer.Argument(..., help="Entry UID to delete."),
    user: str = _user_option,
) -> None:
    """Delete a journal entry."""
    config_path = resolve_config_path(user)
    facade = Facade(config_path, ensure_server=False)
    try:
        deleted = facade.journal.delete_entry(uid)
        if deleted:
            typer.echo(f"Deleted: {uid}")
        else:
            typer.echo(f"Entry '{uid}' not found.", err=True)
            raise typer.Exit(code=1)
    finally:
        facade.shutdown()


@app.command()
def ui(
    user: str = _user_option,
    port: int = typer.Option(3001, "--port", "-p", help="Port for the Streamlit server."),
    host: str = typer.Option("0.0.0.0", "--host", help="Interface for the Streamlit server to bind to."),
) -> None:
    """Start the Streamlit UI."""
    config_path = resolve_config_path(user)
    os.environ[CONFIG_PATH_ENV] = str(config_path.resolve())

    # Launch streamlit, pointing it at the UI module
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        "src/agent_context/ui/app.py",
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
    ]
    sys.exit(stcli.main())


def main() -> None:
    app()


def main_ui() -> int:
    """Console-script entry point for ``gac-ui``.

    Starts Streamlit for the default user. Honors ``GAC_UI_PORT``
    (default 3001) and ``GAC_UI_HOST`` (default 0.0.0.0).

    Implementation note: this entry point ``execvp``s into ``streamlit
    run`` rather than spawning it as a subprocess. The previous
    ``subprocess.call`` approach added a Python wrapper layer between
    the shell and streamlit; when the shell sent SIGINT to its
    process group (``kill 0``), the wrapper died but the streamlit
    process was reparented to PID 1 and stopped responding to the
    signal, leaving bash's ``wait`` blocked. Replacing the wrapper
    with streamlit keeps the process tree flat, so signals reach
    streamlit directly.
    """
    from ..configs import CONFIG_PATH_ENV, DEFAULT_USER, resolve_config_path

    config_path = resolve_config_path(DEFAULT_USER)
    os.environ[CONFIG_PATH_ENV] = str(config_path.resolve())

    # Run the ASGI wrapper (not app.py directly) so the
    # /api/session/{login,logout} cookie routes are mounted —
    # the auth forms' JS fetches those endpoints to persist the
    # session cookie (ADR-021).
    app_path = Path(__file__).resolve().parent.parent / "ui" / "asgi_app.py"
    port = os.environ.get("GAC_UI_PORT", "3001")
    host = os.environ.get("GAC_UI_HOST", "0.0.0.0")

    argv = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        port,
        "--server.headless",
        "true",
    ]
    os.execvp(sys.executable, argv)
    return 1


if __name__ == "__main__":
    main()
