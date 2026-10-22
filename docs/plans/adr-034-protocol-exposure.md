# Plan for adr-034

## Steps

1. Create src/agent_context/api/routers/_profile_ops.py:
   - Move the read / write / edit / history / restore handlers out of
     routers/profile.py into plain functions that take an explicit target.
   - Keep the error mapping (404 missing file, 400 bad oldText, 400 bad
     version) identical to the current behaviour.

2. Refactor src/agent_context/api/routers/profile.py:
   - Keep the six routes and the `{target}` path parameter.
   - Delegate to the shared ops.

3. Create src/agent_context/api/routers/protocol.py:
   - Router at prefix `/protocol`, tag `protocol`, pinned to
     ProfileTarget.PROTOCOL.
   - Routes: GET/PUT/PATCH "", GET /history, POST /restore.

4. Update src/agent_context/api/app.py:
   - Include the protocol router.

5. Create src/agent_context/cli/profile.py:
   - `gac profile` group: list, read, write, edit, history, restore with the
     target as an argument.
   - `gac protocol` group: read, write, edit, history, restore pinned to the
     operating protocol.
   - Commands work on the local store through the Facade.

6. Update src/agent_context/cli/app.py:
   - Register both groups.

7. Update tests/test_profile_api.py:
   - Add tests for the dedicated /protocol routes (read, write, edit, history,
     restore, auth, per-user isolation, parity with /profile/protocol).

8. Create tests/test_profile_cli.py:
   - Add tests for both CLI groups.

9. Update stale docstrings that still say "life story" / "life_story" now that
   the second target is the protocol.

10. Update README.md with the new CLI commands and the /protocol routes.

11. Run make lint, make typecheck, make test.
