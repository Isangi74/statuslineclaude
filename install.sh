#!/usr/bin/env sh
# statuslineclaude installer (Linux, macOS, WSL, Git Bash).
#
# Thin wrapper: locates a Python interpreter and hands over to install.py,
# where the actual logic lives.
#
#   ./install.sh              install or update
#   ./install.sh --uninstall  remove it again
#   ./install.sh --dry-run    show what would change
set -eu

# Redirecting cd keeps CDPATH from echoing the directory into the result.
DIR=$(cd -- "$(dirname -- "$0")" >/dev/null 2>&1 && pwd)

for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON=$candidate
    break
  fi
done

if [ -z "${PYTHON:-}" ]; then
  echo "error: Python 3.9+ is required but neither 'python3' nor 'python' is on PATH." >&2
  echo "       Install it and try again (see the README for per-OS instructions)." >&2
  exit 1
fi

exec "$PYTHON" "$DIR/install.py" "$@"
