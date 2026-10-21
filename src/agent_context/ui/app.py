"""Streamlit entry script for the agent-context UI.

Sets the page config, configures the sidebar navigation, and runs
the selected page. Authentication is not gated in this script;
``agent_context.ui._state.get_facade`` is the single source of truth and
self-heals when called without an authenticated user (it shows
the login form inline and stops the page module).
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_UI_DIR = Path(__file__).parent
_PAGES = _UI_DIR / "pages"


def _page(path: Path, title: str, icon: str, url_path: str) -> st.Page:
    return st.Page(str(path), title=title, icon=icon, url_path=url_path)


st.set_page_config(
    page_title="agent-context",
    layout="wide",
    page_icon=":material/bolt:",
)

from agent_context.ui._auth import rehydrate_session, render_logout_button  # noqa: E402

rehydrate_session()
render_logout_button()

nav: dict[str, list[st.Page]] = {
    "Context": [
        _page(_PAGES / "journal.py", "Journal", ":material/article:", "journal"),
        _page(_PAGES / "profile.py", "Profile", ":material/person:", "profile"),
    ],
    "Account": [
        _page(_PAGES / "settings.py", "Settings", ":material/settings:", "settings"),
    ],
}

st.navigation(nav).run()
