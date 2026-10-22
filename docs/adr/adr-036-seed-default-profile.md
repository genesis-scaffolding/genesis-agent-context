# 036. Seed default profile documents at account creation

## Context

The profile store (ADR-025) serves two per-user markdown documents: the
agent persona (`profile`) and the agent operating protocol (`protocol`,
ADR-031). Both start life as nothing. A newly created account therefore
has no persona and no protocol until somebody writes them, and until then
every read of `/profile/profile` or `/protocol` is a 404 and the agent
serving that account has no operating context.

That is fine for a single-user install where the owner curates the
documents by hand. It stops being fine the moment the system serves a
household. The second account (`alisa`, say) is created from the sign-up
form, and the first thing she meets is an empty store. The first account's
documents were written by hand over months; nobody is going to do that
again for every new person.

Seeding has to satisfy three constraints:

1. **Write once.** Seeding on every login would silently revert edits. The
   user edits their persona, logs out, logs in, and the edit is gone.
2. **Do not clobber.** A re-created account (`delete_user` then
   `create_user`; `delete_user` deliberately leaves the Radicale
   collection tree on disk, and the profile root is separate) must not have
   its documents replaced.
3. **Go through the normal write path.** Writing the files straight to
   disk would skip the snapshot machinery (ADR-025), so the seeded state
   would have no version 1 in history and could not be restored or
   distinguished from a hand-written document.

There is also a content constraint: the documents that exist today on the
`gentran1991` account are one user's, written for one person's assistant.
Shipping them verbatim as the default would put another person's voice,
pronouns and history into a stranger's account.

## Decision

### Seed package

New package `src/agent_context/seed/`:

```
src/agent_context/seed/
  __init__.py     re-export the seed surface
  documents.py    maps a profile target to its packaged markdown file
  profile.md      the default persona
  protocol.md     the default operating protocol
  facade.py       seed_new_account(): resolve root, write what is missing
```

The markdown files are packaged data beside the module that reads them,
named after the profile target they seed, so the mapping to
`agent_context.profile.TARGETS` is one-to-one. They ship inside the
editable install and inside the image (both mount or copy `src/`).

### Where the seed is applied

One place: `agent_context.users.create_user`, the module-level wrapper that
is the single account-creation path in the system. The UI sign-up form and
`docker-bootstrap.sh` both go through it; `UserStore.add` is the
lower-level table primitive and does not seed.

Not on login, not on first request, not in the API read path. Login is the
wrong hook by construction: it runs forever, on every login, so it cannot
distinguish "brand new account" from "account with a year of edits".

Order inside `create_user` is: users table, then htpasswd, then seed. The
seed runs last so an account whose stores did not both come into existence
is not left with seeded documents.

### How the documents are written

`seed_new_account(username)` resolves the user's profile root by building a
`Configs` from the user's `configs.yaml` path (new pure helper
`agent_context.configs.config_path_for`, split out of `resolve_config_path`
so the seed reads config without creating directories), then walks
`TARGETS`:

- canonical file already exists → skip, record in `skipped`
- otherwise → `ProfileFacade.write(target, seed, note="seed: ...")`

`ProfileFacade.write` is the existing public write path, so the seeded
content lands as snapshot version 1 with `command="write"` and a seed note.
History, restore and the API behave identically to any other first write.

A `documents: dict[ProfileTarget, str]` parameter overrides the packaged
content per target. A future per-user seed (a document chosen at signup, a
tenant default) is a caller-supplied mapping, not a code change.

### Failure policy

`create_user` does not raise when seeding fails. By the time the seed runs,
the account exists in the users table and the htpasswd; refusing to report
success would show a failed signup for an account the user cannot then
create again (duplicate username) or reach. An empty profile root is
recoverable by hand.

Per-target failures come back in `SeedResult.errors` and `create_user` logs
them at warning level. Surfaced, not silent; not fatal.

### Content

The two seed documents are the current `gentran1991` documents with the
user-specific content generalised:

- Address the user as "the user" / "them", never a name, never gendered
  pronouns.
- Drop the attribution that the mindset principles come from the user's own
  life system, and keep the principles themselves.
- Keep the agent name (Max), the structure, the style bans, the working
  rules, the protocol sections and their wording.
- Add nothing. The seed is the existing document, sanitised, so the diff
  between an account's own documents and the seed is exactly the personal
  content a user would want to rewrite.

## Status

Accepted

## Consequences

Positive:

- A new account is immediately usable: `/profile` lists two existing
  documents, the agent has a persona and an operating protocol from its
  first request.
- The seeded state is a normal version 1, so restore, history and the API
  need no special cases.
- No clobber risk on login, on re-creation, or from a per-user override.
- Seed content is versioned in git like code. Improving the baseline is a
  normal reviewable change, and users keep whatever they have already.

Negative:

- Every new account starts from a document someone else wrote, and a
  persona that is wrong for them is worse than an empty one until they
  rewrite it. Mitigation: the content is a general baseline, the first
  snapshot is restorable, and nothing else in the system assumes the
  baseline is correct.
- Accounts created before this ADR have no seed and are not backfilled.
  Backfill would mean overwriting or shadowing hand-written documents, so
  it is deliberately out of scope. Existing accounts are unaffected.
- Seeding writes to a second location during signup. A read-only or
  misconfigured data mount shows up as a logged warning, not a failed
  signup. That is the deliberate trade above.

Neutral:

- The profile store is unchanged. `seed` depends on `profile` and
  `configs`; nothing in `profile` knows the seed exists.
- `UserStore.add` still does not seed. Tests that build a store directly
  (the API test fixture, migrations) are unaffected and keep their empty
  profile roots.