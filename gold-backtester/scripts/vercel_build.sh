#!/bin/sh
# Vercel build step: rebuild the website from the strategy cards in the repo.
# If Python is missing or the build fails, the committed copy in public/ is served unchanged.
cd "$(dirname "$0")/.." || exit 0
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 not found: serving the committed site"; exit 0
fi
DEPS="numpy pandas requests pyyaml markdown"
python3 -m pip install --quiet $DEPS 2>/dev/null || python3 -m pip install --quiet --break-system-packages $DEPS || {
  echo "pip install failed: serving the committed site"; exit 0; }
python3 -m goldlab site --out public || echo "site build failed: serving the committed site"
exit 0
