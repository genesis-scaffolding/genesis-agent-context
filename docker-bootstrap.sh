#!/bin/sh
# First-boot user bootstrap, run as the dropped-privilege user by
# docker-entrypoint.sh. Creates the bootstrap account if the users table
# does not exist yet. Idempotent: an existing table means the container
# has already been initialised and nothing is touched.
set -e

state_home="${XDG_STATE_HOME:-$HOME/.local/state}"
users_yaml="$state_home/agent-context/users.yaml"

[ -f "$users_yaml" ] && exit 0

gac user create "$GAC_BOOTSTRAP_USER" --password "$GAC_BOOTSTRAP_PASSWORD"
