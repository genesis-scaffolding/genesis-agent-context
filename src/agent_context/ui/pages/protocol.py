"""Protocol page: the agent operating protocol.

Thin wrapper around :func:`agent_context.ui._profile_page.render`.
Target = ``protocol``; the page title, caption, and empty-state
hint are the only thing this file owns.
"""

from __future__ import annotations

from agent_context.profile import ProfileTarget
from agent_context.ui._profile_page import render

render(
    target=ProfileTarget.PROTOCOL,
    title="Protocol",
    caption="The agent's operating rules: delegation policies, working session rules, etc.",
    empty_hint=(
        "No protocol yet. Write the agent's operating protocol here — "
        "delegation policies, working session rules, and other guidelines "
        "that shape how the agent works with you. You can edit this any time."
    ),
    key_prefix="protocol",
)
