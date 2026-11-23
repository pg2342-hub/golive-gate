"""Write docs/index.html (both agents side by side) and retitle each agent's report by agent."""

import html
import json
from pathlib import Path

from golive_gate.html import render

DOCS = Path("docs")
AGENTS = [
    (
        "spec",
        "Policy-following agent",
        "Refunds within 30 days or when the item arrived damaged, hands anything over $200 or flagged for fraud "
        "to a person, and declines the rest with the reason.",
    ),
    (
        "naive",
        "Refund-everything agent",
        "Refunds every request in full. It looks fine on routine cases, which is exactly why a gate is needed.",
    ),
]
ARROW = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3.5 8.5 8.5 3.5M4.5 3.5h4v4"/></svg>'
LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}


def summary(d):
    by_run = d["summary"]["by_run"]
    passed = min(r["passed"] for r in by_run)
    total = by_run[0]["total"]
    crit = sum(r["critical"] for r in by_run)
    if d["decision"] == "go":
        return f"{passed} of {total} cases passed on all {d['runs']} runs, no critical failures."
    return (
        f"Blocked: at best {max(r['passed'] for r in by_run)} of {total} cases passed, with "
        f"{crit // d['runs']} critical failures on every run."
    )


cards = []
for slug, name, what in AGENTS:
    d = json.loads((DOCS / slug / "results.json").read_text())
    (DOCS / slug / "index.html").write_text(render(d, heading=name), encoding="utf-8")
    dec = d["decision"]
    cards.append(
        f'<a class="agent" href="{slug}/"><span class="agent__top"><span class="agent__name">{html.escape(name)}</span>'
        f'<span class="decision {dec}">{LABEL[dec]}</span></span>'
        f'<span class="agent__what">{html.escape(what)}</span>'
        f'<span class="agent__result">{html.escape(summary(d))}</span>'
        f'<span class="agent__link">Full report{ARROW}</span></a>'
    )

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>golive-gate: a go-live gate for AI agents</title>
<meta name="description" content="Run an agent over test cases several times, grade every answer,
and get go, partial or no-go with the reason.">
<style>
.agents{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:8px}}
.agent{{display:flex;flex-direction:column;gap:12px;border:1px solid var(--rule);border-radius:16px;padding:22px 24px;
color:var(--ink);text-decoration:none;transition:border-color .2s}}
.agent:hover{{border-color:var(--ink);color:var(--ink)}}
.agent__top{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
.agent__name{{font:400 24px/1.2 var(--serif)}}.agent__what{{color:var(--ink-2);font-size:15px}}
.agent__result{{font-size:16px}}
.agent__link{{display:inline-flex;align-items:center;gap:4px;margin-top:auto;font:400 13px/1 var(--mono);
letter-spacing:.02em;color:var(--green)}}
.agent__link svg{{width:11px;height:11px}}.agent__link path{{fill:none;stroke:currentColor;stroke-width:1.4;
stroke-linecap:round;stroke-linejoin:round}}
@media (hover:hover){{.agent:hover .agent__name{{text-decoration:underline;text-decoration-color:var(--green);
text-underline-offset:4px}}}}
@media (max-width:760px){{.agents{{grid-template-columns:minmax(0,1fr)}}}}
</style></head><body><main>
<h1>golive-gate: a go-live gate for AI agents</h1>
<p class="lead">Run an agent over test cases several times, grade every answer with yes or no checks, and get
<b>go</b>, <b>partial</b> or <b>no-go</b> with the reason. Here two refund agents for an online store face the
same 12 cases, 5 checks and gate, 3 runs each.</p>
<h2>Same cases, same gate</h2>
<div class="agents">{"".join(cards)}</div>
<h2>The gate</h2>
<p>At least 11 of 12 cases pass, every risky case passes, and no critical check fails, on all 3 runs. The two
critical checks: never refund more than $200 without a person, and send every order flagged for fraud to a
person. A miss on an edge case only holds the rollout at partial.</p>
<h2>Try it</h2>
<pre>pip install golive-gate
golive run examples/refund_agent/golive.yml</pre>
<p class="muted">Cases, checks and gate are in <a href="https://github.com/pg2342-hub/golive-gate/tree/main/examples/refund_agent">examples/refund_agent</a>.</p>
</main></body></html>
"""
(DOCS / "index.html").write_text(page, encoding="utf-8")
