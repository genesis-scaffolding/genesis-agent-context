"""Profile page: who you are.

Thin wrapper around :func:`agent_context.ui._profile_page.render`.
Target = ``profile``; the page title, caption, and empty-state
hint are the only thing this file owns.
"""

from __future__ import annotations

from agent_context.profile import ProfileTarget
from agent_context.ui._profile_page import render

render(
    target=ProfileTarget.PROFILE,
    title="Profile",
    caption="Tell us about you. We use this to personalize your assistant.",
    empty_hint=(
        "No profile yet. Write a few lines about yourself — your name, "
        "timezone, what you do, anything that helps your assistant "
        "understand you. You can edit this any time."
    ),
    key_prefix="profile",
)
