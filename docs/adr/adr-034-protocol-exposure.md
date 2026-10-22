# 034. Protocol as a first-class entity: dedicated API routes and CLI group

## Context

ADR-031 turned the profile store into two targets: `profile` (the persona) and
`protocol` (the agent operating protocol). The store, the facade, the backup
exporter, and the Streamlit UI all treat the two targets equally, but the two
surfaces an agent actually talks to did not:

- **API.** The protocol was only reachable as `/profile/protocol`, a path
  parameter on the persona's router. There was no route where the operating
  protocol appears as an entity in its own right, so it was missing from the
  OpenAPI document's tags and an agent had to know the internal target spelling
  to reach it.
- **CLI.** `gac` exposed journals and user management only. Neither the persona
  nor the operating protocol had a command surface, so the profile store was
  unreachable from the command line entirely.

The UI already gave the protocol its own page (`ui/pages/protocol.py`), which
made the asymmetry visible: the protocol was a first-class entity in the UI and
a second-class target everywhere else.

## Decision

We will expose the operating protocol the same way the persona is exposed.

### API

Add a dedicated router mounted at `/protocol`, pinned to
`ProfileTarget.PROTOCOL`:

| Method | Path              | Equivalent profile route |
|--------|-------------------|--------------------------|
| GET    | `/protocol`       | `GET /profile/protocol`  |
| PUT    | `/protocol`       | `PUT /profile/protocol`  |
| PATCH  | `/protocol`       | `PATCH /profile/protocol`|
| GET    | `/protocol/history`   | `GET /profile/protocol/history`   |
| POST   | `/protocol/restore`   | `POST /profile/protocol/restore`   |

The generic `/profile/{target}` routes stay exactly as they are. Both routers
call the same implementation in `api/routers/_profile_ops.py`, so the two
surfaces cannot drift apart in behaviour or error mapping.

### CLI

Add a `gac profile` group covering the store generically (the target is an
argument: `profile` or `protocol`) and a `gac protocol` group with the same
operations pinned to the operating protocol:

```
gac profile list|read|write|edit|history|restore
gac protocol read|write|edit|history|restore
```

The CLI works on the local store through the `Facade`, the same way the journal
commands do. It is not an HTTP client.

### Entity naming

The `protocol` target keeps its wire and CLI spelling. The persona keeps the
`profile` target spelling in the store (its display name, "Persona", stays a
UI concern).

## Status

Accepted

## Consequences

Positive:

- The operating protocol is a first-class entity on every surface: UI page, API
  routes, CLI group.
- The API and the CLI expose the same operations, and the persona and the
  protocol expose the same operations as each other.
- One shared implementation (`_profile_ops.py`) means the two API surfaces
  cannot drift.

Negative:

- Two ways to reach the protocol over HTTP (`/protocol` and
  `/profile/protocol`). The duplicate is deliberate: the generic route stays for
  the store-level interface, the pinned route is the entity-level one.
- The CLI grew a second target-aware group. `gac profile <cmd> protocol` and
  `gac protocol <cmd>` do the same thing; the first is the store interface, the
  second is the entity shortcut.
