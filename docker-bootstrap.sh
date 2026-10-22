#!/bin/sh
# First-boot user bootstrap, run as the dropped-privilege user by
# docker-entrypoint.sh. Creates the bootstrap account if the users table
# does not exist yet. Idempotent: an existing table means the container
# has already been initialised and nothing is touched.
set -e

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
users_yaml="$state_home/agent-context/users.yaml"

[ -f "$users_yaml" ] && exit 0

# Create the bootstrap account through the users API (the agent-facing
# CLI ships separately, so there is no `gac user create` in this image).
python - <<'PY'
import os

from agent_context.users import create_user

username = os.environ["GAC_BOOTSTRAP_USER"]
password = os.environ["GAC_BOOTSTRAP_PASSWORD"]
create_user(username, password)
print(f"Created bootstrap user '{username}'.")
PY
