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

5. Update stale docstrings that still say "life story" / "life_story" now that
   the second target is the protocol.

6. Update README.md with the /protocol routes.

7. Run make lint, make typecheck, make test.

Note: the original plan also created `src/agent_context/cli/profile.py` and
`tests/test_profile_cli.py`. Both were dropped before this plan landed:
ADR-035 purged the in-repo CLI entirely, and the agent-facing CLI ships in the
my-agent-skills repo over the REST API.
