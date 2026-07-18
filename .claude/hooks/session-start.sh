#!/bin/bash
set -euo pipefail

# Prepare a Claude Code on the web session so the CI gates run out of the box.
# Local developers manage their own venv, so this only runs in the remote
# environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Install into a project virtualenv so the pinned dependency tree resolves
# cleanly regardless of any distro-managed system Python packages, and survives
# in the cached container. Reused (not recreated) when a session resumes.
VENV="$CLAUDE_PROJECT_DIR/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip

# App deps (requirements.txt) run the tests; the CLI deps (requirements-cli.txt)
# plus playwright let pylint resolve every import in the linted tree; pylint,
# pip-audit and bandit are the lint/security gates themselves. Matches the
# commands documented in CLAUDE.md, so `python -m unittest discover`, pylint,
# pip-audit and bandit all work without further setup.
"$VENV/bin/pip" install -r requirements.txt -r requirements-cli.txt playwright pylint pip-audit bandit

# Put the venv first on PATH for the rest of the session, so `python`, `pylint`,
# `pip-audit` and `bandit` resolve to the versions installed above.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export PATH=\"$VENV/bin:\$PATH\"" >> "$CLAUDE_ENV_FILE"
fi
