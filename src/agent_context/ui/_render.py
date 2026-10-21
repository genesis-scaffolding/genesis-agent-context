"""Shared Streamlit widgets and dialogs for the agent-context UI.

Page modules call these to render consistent status pills and to open
dialogs. The dialogs are streamlit-decorated functions; pages call them
directly from a button body (or ``on_click`` callback).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import streamlit as st

from agent_context.journal.facade import Entry
from agent_context.ui._state import get_facade

logger = __import__("logging").getLogger(__name__)


# -----------------------------------------------------------------------------
# Delete confirm dialog
# -----------------------------------------------------------------------------


@st.dialog("Confirm delete", on_dismiss="rerun")
def delete_confirm_dialog(label: str, callback: Callable[[], Any]) -> None:
    """Open the delete-confirmation dialog. Call from a button body.

    ``label`` is the human-readable name of the thing being deleted.
    ``callback`` runs on confirmation.
    """
    st.write(f"Delete **{label}**? This cannot be undone.")
    cols = st.columns(2)
    if cols[0].button("Delete", type="primary", key=f"delcfm_{label}"):
        callback()
        st.rerun()
    if cols[1].button("Cancel", key=f"delcn_{label}"):
        st.rerun()


# -----------------------------------------------------------------------------
# Journal view helper
# -----------------------------------------------------------------------------


def render_journal_entry_view(
    entry: Entry,
    *,
    on_edit: Callable[[Entry], None] | None = None,
    show_delete: bool = False,
) -> None:
    """Render the view-only display of a journal entry.

    Renders the title row, the markdown body (or an "Empty entry."
    caption), and an Edit button. With ``show_delete=True`` also
    renders a Delete button that opens :func:`delete_confirm_dialog`.
    """
    title_text = entry.title or entry.date.strftime("%A, %B %d, %Y")
    title_row = st.container(horizontal=True, vertical_alignment="center")
    with title_row:
        st.markdown(f"## {title_text}")
        if entry.type is not None:
            st.badge(entry.type.value, color="blue")

    if entry.content.strip():
        st.markdown(entry.content)
    else:
        st.caption("Empty entry.")

    st.divider()
    st.write("")
    if st.button(
        "Edit",
        key=f"jev_edit_{entry.uid}",
        icon=":material/edit:",
        type="primary",
    ):
        if on_edit is not None:
            on_edit(entry)
        else:
            st.query_params["edit"] = "1"
            st.rerun()
    if show_delete:
        if st.button(
            "Delete",
            key=f"jev_del_{entry.uid}",
            icon=":material/delete:",
        ):
            delete_confirm_dialog(
                f"entry {entry.date.isoformat()}",
                lambda: get_facade().journal.delete_entry(entry.uid),
            )
