#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")"
if [ ! -f .venv/bin/activate ]; then
    echo "LockIn's virtual environment is missing. Follow the setup in README.md." >&2
    exit 1
fi
. .venv/bin/activate
exec python -m daemon.vision --menubar "$@"
