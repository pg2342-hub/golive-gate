#!/usr/bin/env bash
# Rebuild the GitHub Pages demo in docs/: an intro page with both refund agents side by side,
# and a full report for each (docs/spec/ passes the gate, docs/naive/ is blocked).
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf docs/naive docs/spec docs/index.html docs/results.json
golive run examples/refund_agent/golive.yml --out docs/spec >/dev/null
golive run examples/refund_agent/golive.yml --agent agent:naive_agent --out docs/naive >/dev/null || true
rm -f docs/spec/report.md docs/naive/report.md
python scripts/demo_intro.py
python scripts/demo_chrome.py docs/index.html docs/spec/index.html docs/naive/index.html --repo golive-gate
touch docs/.nojekyll
echo "demo written to docs/ (intro), docs/spec/ and docs/naive/"
