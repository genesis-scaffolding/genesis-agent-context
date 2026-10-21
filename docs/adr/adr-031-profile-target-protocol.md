# 031. Profile targets: drop life_story, add protocol

## Context

The profile store (ADR-025) was designed with two targets: `profile` (agent persona)
and `life_story` (user narrative history). The brief's approved decision replaces
`life_story` with `protocol`: a second agent-context document holding the agent's
operating protocol (delegation policies, working session rules, etc.).

The resulting system has exactly two targets: `profile` (agent persona) and `protocol`
(agent operating protocol).

## Decision

### ProfileTarget enum

Remove `ProfileTarget.LIFE_STORY`. Add `ProfileTarget.PROTOCOL`.

Old:
```
PROFILE = "profile"
LIFE_STORY = "life_story"
```

New:
```
PROFILE = "profile"
PROTOCOL = "protocol"
```

### Filenames

- `profile.md` — unchanged.
- `protocol.md` — replaces `life-story.md`.

Old `TARGET_FILENAME`:
```python
TARGET_FILENAME = {
    ProfileTarget.PROFILE: "profile.md",
    ProfileTarget.LIFE_STORY: "life-story.md",
}
```

New `TARGET_FILENAME`:
```python
TARGET_FILENAME = {
    ProfileTarget.PROFILE: "profile.md",
    ProfileTarget.PROTOCOL: "protocol.md",
}
```

### TARGETS constant

Old: `(PROFILE, LIFE_STORY)`
New: `(PROFILE, PROTOCOL)`

### Snapshot directory names

`versions_dir` uses `target.value` for the subdirectory name, so `.versions/profile/` is
unchanged and `.versions/life_story/` is replaced by `.versions/protocol/`.

### API layer

`ProfileWireTarget` is a re-export of `ProfileTarget`, so wire values automatically
become `"profile"` and `"protocol"`. Unknown targets (including `life_story`) return 404.

### UI layer

- `ui/pages/profile.py` renders the `profile` target with Persona-specific copy.
- A new `ui/pages/protocol.py` renders the `protocol` target, reusing `_profile_page.render`.
- Navigation is updated to: Persona / Protocol / Memory (plus Settings).

Streamlit nav:
```
Persona: [Persona]
Context: [Memory, Protocol]
Account: [Settings]
```

### Tests

All tests referencing `LIFE_STORY`, `"life_story"`, or `"life-story.md"` are updated
to `PROTOCOL`, `"protocol"`, or `"protocol.md"`.

### Migration

Old `life-story.md` files are not renamed. Users with existing data must migrate it
manually. This is explicitly out of scope for this ADR.

## Status

Accepted

## Consequences

Positive:
- Exactly two targets, both with the same versioning machinery.
- `protocol` is the agent's operating context document alongside the persona.

Negative:
- Existing `life-story.md` files are orphaned (no auto-migration).
