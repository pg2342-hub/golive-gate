#!/usr/bin/env bash
# Rebuild the GitHub Pages demo in docs/ from the refund agent example.
set -euo pipefail
cd "$(dirname "$0")/.."
golive run examples/refund_agent/golive.yml --agent agent:naive_agent --out docs >/dev/null || true
golive run examples/refund_agent/golive.yml --out docs/spec >/dev/null
rm -f docs/report.md docs/spec/report.md
# Link the two pages to each other.
python - <<'PY'
from pathlib import Path
notes = {
    "docs/index.html": "Demo of <a href='https://github.com/pg2342-hub/golive-gate'>golive-gate</a>: a refund agent that "
    "refunds everything passes every routine case and is still blocked. "
    "<a href='spec/'>See the policy-following agent pass the same gate</a>.",
    "docs/spec/index.html": "The policy-following refund agent on the same cases and gate. "
    "<a href='../'>See the naive agent get blocked</a>.",
}
for path, note in notes.items():
    p = Path(path)
    p.write_text(p.read_text().replace("</h1>", f"</h1>\n<p class='lead'>{note}</p>", 1))
PY
python scripts/demo_chrome.py docs/index.html docs/spec/index.html --repo golive-gate
touch docs/.nojekyll
echo "demo written to docs/ (naive agent) and docs/spec/ (reference agent)"
