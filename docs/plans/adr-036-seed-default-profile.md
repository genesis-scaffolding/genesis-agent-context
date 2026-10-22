# Plan for adr-036

## Steps

1. Add `config_path_for(user)` to `src/agent_context/configs.py` as a pure
   resolver; make `resolve_config_path` call it. Seed needs the per-user
   config path without creating directories.
2. Add `src/agent_context/seed/profile.md` and `protocol.md`: the current
   persona and operating protocol, sanitised (no name, no gendered
   pronouns, no personal attribution).
3. Add `src/agent_context/seed/documents.py`: target -> packaged file
   mapping and a loader.
4. Add `src/agent_context/seed/facade.py`: `SeedResult`,
   `profile_root_for`, `seed_new_account`. Writes missing targets through
   `ProfileFacade.write`, skips existing ones, never raises.
5. Add `src/agent_context/seed/__init__.py` re-exporting the surface.
6. Call `seed_new_account` at the end of `create_user` in
   `src/agent_context/users/store.py`, logging any errors.
7. Tests in `tests/test_users_unit.py`: both documents seeded at the right
   paths for a new account, the seed recorded as snapshot version 1, an
   existing document survives a re-created account, and the
   written/skipped report.
8. Run `make lint`, `make typecheck`, `uv run pytest`.
9. Document: ADR-036, this plan, README (architecture tree + first account).