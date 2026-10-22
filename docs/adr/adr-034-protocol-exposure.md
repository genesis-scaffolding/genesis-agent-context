# 034. Protocol as a first-class entity: dedicated API routes

## Context

ADR-031 turned the profile store into two targets: `profile` (the persona) and
`protocol` (the agent operating protocol). The store, the facade, the backup
exporter, and the Streamlit UI all treat the two targets equally, but the
surface an agent actually talks to did not:

- **API.** The protocol was only reachable as `/profile/protocol`, a path
  parameter on the persona's router. There was no route where the operating
  protocol appears as an entity in its own right, so it was missing from the
  OpenAPI document's tags and an agent had to know the internal target spelling
  to reach it.

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

### Entity naming

The `protocol` target keeps its wire spelling. The persona keeps the
`profile` target spelling in the store (its display name, "Persona", stays a
UI concern).

## Status

Accepted

## Consequences

Positive:

- The operating protocol is a first-class entity on every surface: UI page and
  API routes.
- The persona and the protocol expose the same operations as each other.
- One shared implementation (`_profile_ops.py`) means the two API surfaces
  cannot drift.

Negative:

- Two ways to reach the protocol over HTTP (`/protocol` and
  `/profile/protocol`). The duplicate is deliberate: the generic route stays for
  the store-level interface, the pinned route is the entity-level one.
