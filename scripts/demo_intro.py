"""Write docs/index.html (both agents side by side) and retitle each agent's report by agent."""

import html
import json
from pathlib import Path

from golive_gate.cases import load_cases
from golive_gate.html import render

DOCS = Path("docs")
REPO = "https://github.com/pg2342-hub/golive-gate"
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
GROUPS = [("routine", "Routine"), ("edge", "Edge"), ("risky", "Risky")]
ARROW = '<svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3.5 8.5 8.5 3.5M4.5 3.5h4v4"/></svg>'
LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}
BADGE = {"go": "go", "partial": "partial", "no-go": "nogo"}
BACK = (
    "<style>.back{display:inline-flex;align-items:center;gap:6px;margin-top:32px;font:400 13px/1 var(--mono);"
    "letter-spacing:.02em;color:var(--green);text-decoration:none}.back:hover{text-decoration:underline;"
    "text-underline-offset:3px}.back svg{width:11px;height:11px}.back path{fill:none;stroke:currentColor;"
    "stroke-width:1.4;stroke-linecap:round;stroke-linejoin:round}.back+h1{margin-top:20px}</style>"
    '<a class="back" href="../"><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5"/></svg>'
    "Back to golive-gate</a>"
)
e = html.escape


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


def state(d, case_run):
    if case_run["passed"]:
        return "pass", "passed"
    crit = {c["id"] for c in d["checks"] if c["critical"]}
    if crit & set(case_run["failed_checks"]):
        return "crit", "failed a critical check"
    return "fail", "failed"


def grid(d, name):
    """One row per run, one square per case, grouped routine / edge / risky."""
    rows = []
    for i in range(d["runs"]):
        groups = []
        for g, _label in GROUPS:
            cells = []
            for c in (c for c in d["cases"] if c["group"] == g):
                st, words = state(d, c["runs"][i])
                cells.append(
                    f'<a class="cell {st}" href="#case-{c["id"]}" data-case="{c["id"]}" '
                    f'aria-label="{e(name)}, run {i + 1}, case {c["id"]} ({e(c["title"])}) {words}"></a>'
                )
            groups.append(f'<div class="cg">{"".join(cells)}</div>')
        rows.append(f'<div class="run"><span class="rl">Run {i + 1}</span>{"".join(groups)}</div>')
    heads = "".join(f'<span class="gh">{label} 4</span>' for _, label in GROUPS)
    return (
        f'<div class="grid" role="group" aria-label="{e(name)}: every case on every run">{"".join(rows)}'
        f'<div class="run heads"><span class="rl"></span>{heads}</div></div>'
    )


def rules(d):
    out = []
    for name in ("overall", "risky cases", "edge cases"):
        rs = [r for r in d["gate_result"]["rules"] if r["name"] == name]
        held = all(r["held"] for r in rs)
        worst = min(r["passed"] for r in rs)
        out.append(
            f'<li class="{"held" if held else "broke"}"><span>{e(name.capitalize())}</span>'
            f"<b>{worst} of {rs[0]['total']}</b><small>needs {rs[0]['required']}</small>"
            f"<em>{'held' if held else 'broke'}</em></li>"
        )
    crit = sum(r["critical"] for r in d["summary"]["by_run"]) // d["runs"]
    out.append(
        f'<li class="{"held" if crit == 0 else "broke"}"><span>Critical checks</span><b>{crit} failed</b>'
        f"<small>needs 0</small><em>{'held' if crit == 0 else 'broke'}</em></li>"
    )
    return f'<ul class="rules">{"".join(out)}</ul>'


cases = {c.id: c for c in load_cases("examples/refund_agent/cases.yml")}
data, cards = {}, []
for slug, name, what in AGENTS:
    d = json.loads((DOCS / slug / "results.json").read_text())
    data[slug] = d
    report = render(d, heading=name).replace("<main>", "<main>" + BACK, 1)
    (DOCS / slug / "index.html").write_text(report, encoding="utf-8")
    dec = d["decision"]
    worst = min(r["passed"] for r in d["summary"]["by_run"])
    crit = sum(r["critical"] for r in d["summary"]["by_run"]) // d["runs"]
    cards.append(
        f'<article class="agent {BADGE[dec]}"><div class="agent__top"><h3>{e(name)}</h3>'
        f'<span class="gate {BADGE[dec]}">{LABEL[dec]}</span></div>'
        f'<p class="agent__what">{e(what)}</p>'
        f'<div class="agent__score"><b>{worst}</b><span>of 12 cases passed on every run<br>'
        f"{crit} critical failure{'' if crit == 1 else 's'} per run</span></div>"
        f"{grid(d, name)}{rules(d)}"
        f'<p class="agent__result">{e(summary(d))}</p>'
        f'<a class="agent__link" href="{slug}/">Full report{ARROW}</a></article>'
    )

checks = data["spec"]["checks"]
check_rows = "".join(
    f'<tr><td class="n">{e(c["id"])}</td><td>{e(c["text"])}</td>'
    f'<td><span class="sev{" sev-critical" if c["critical"] else ""}">{"Critical" if c["critical"] else "Normal"}'
    "</span></td></tr>"
    for c in checks
)
crit_ids = {c["id"] for c in checks if c["critical"]}


def result_cell(c):
    fails = sorted({f for r in c["runs"] for f in r["failed_checks"]}, key=lambda f: [k["id"] for k in checks].index(f))
    n = sum(r["passed"] for r in c["runs"])
    if not fails:
        return f'<td class="v ok">Pass <span>{n}/3</span></td>'
    crit = bool(crit_ids & set(fails))
    why = ", ".join(fails)
    return f'<td class="v bad{" crit" if crit else ""}">Fail <span>{n}/3</span><div class="why">{why}</div></td>'


rows = []
naive_by = {c["id"]: c for c in data["naive"]["cases"]}
for c in data["spec"]["cases"]:
    case = cases[c["id"]]
    rows.append(
        f'<tr id="case-{c["id"]}" data-g="{c["group"]}"><td class="n">{c["id"]}</td>'
        f'<td><span class="tag">{c["group"]}</span></td><td>{e(c["title"])}</td>'
        f"<td>{e(str(case.expected['action']).capitalize())}</td>"
        f"{result_cell(c)}{result_cell(naive_by[c['id']])}</tr>"
    )
seg = "".join(
    f'<button type="button" role="radio" aria-checked="false" data-g="{g}">{label}&nbsp; <span>4</span></button>'
    for g, label in GROUPS
)

CSS = """
.head h1{margin:40px 0 14px}
.head .lead{max-width:40em}
.verdict{margin:32px 0 0;border:1px solid var(--rule);border-radius:16px;background:#fbfaf6;overflow:hidden}
.vhead{display:flex;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:8px 24px;
padding:18px 24px;border-bottom:1px solid var(--rule)}
.vhead h2{all:unset;font:400 22px/1.2 var(--serif)}
.vhead p{margin:0;color:var(--ink-2);font-size:15px}.vhead p b{color:var(--ink)}
.agents{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}
.agent{display:flex;flex-direction:column;gap:18px;padding:24px;min-width:0}
.agent+.agent{border-left:1px solid var(--rule)}
.agent__top{display:flex;align-items:center;justify-content:space-between;gap:12px}
.agent__top h3{margin:0;font:400 26px/1.15 var(--serif)}
.agent__what{margin:0;color:var(--ink-2);font-size:15px;min-height:4.8em}
.gate{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:0 18px;border-radius:999px;
font:500 16px/1 var(--mono);letter-spacing:.06em;white-space:nowrap}
.gate.go{background:var(--green-wash);color:var(--green)}
.gate.nogo{background:var(--ink);color:var(--paper)}
.gate.partial{border:1.5px dashed var(--ink)}
.agent__score{display:flex;align-items:baseline;gap:12px}
.agent__score b{font:400 64px/1 var(--serif);font-variant-numeric:tabular-nums}
.agent__score span{color:var(--ink-2);font-size:14px;line-height:1.4}
.grid{display:grid;gap:5px}
.run{display:grid;grid-template-columns:3.6em repeat(3,minmax(0,1fr));gap:12px;align-items:center}
.rl{font:400 12px/1 var(--mono);color:var(--ink-2);letter-spacing:.02em}
.cg{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}
.gh{font:400 12px/1.3 var(--mono);color:var(--ink-2);letter-spacing:.02em;padding-top:4px}
.cell{display:block;aspect-ratio:1;border-radius:5px;border:1.5px solid transparent;
transition:transform .2s var(--ease),box-shadow .2s}
.cell.pass{background:var(--green)}
.cell.fail{background:var(--paper);border-color:var(--ink)}
.cell.crit{background:var(--ink)}
.cell:hover,.cell:focus-visible,.cell.lit{transform:translateY(-3px);box-shadow:0 6px 12px -6px rgb(27 26 23/.5)}
.rules{list-style:none;margin:0;padding:0;font-size:14px;border-top:1px solid var(--rule-soft)}
.rules li{display:grid;grid-template-columns:minmax(0,1fr) 5.5em 5em 3.6em;gap:10px;align-items:baseline;margin:0;
padding:8px 0;border-bottom:1px solid var(--rule-soft)}
.rules b{font-weight:500;font-variant-numeric:tabular-nums}
.rules small{color:var(--ink-2);font-size:13px}
.rules em{font:500 12px/1 var(--mono);font-style:normal;letter-spacing:.04em;text-align:right;color:var(--green)}
.rules li.broke em{color:var(--ink)}
.rules li.broke span::before{content:"";display:inline-block;width:8px;height:8px;border-radius:2px;
background:var(--ink);margin-right:8px;vertical-align:1px}
.agent__result{margin:0;font-size:15px}
.agent__link{display:inline-flex;align-items:center;gap:4px;margin-top:auto;font:400 13px/1 var(--mono);
letter-spacing:.02em;color:var(--green);text-decoration:none}
.agent__link:hover{text-decoration:underline}
.agent__link svg{width:11px;height:11px}.agent__link path{fill:none;stroke:currentColor;stroke-width:1.4;
stroke-linecap:round;stroke-linejoin:round}
.legend{display:flex;flex-wrap:wrap;gap:6px 20px;padding:14px 24px;border-top:1px solid var(--rule);
color:var(--ink-2);font-size:13px}
.legend span{display:inline-flex;align-items:center;gap:8px}
.legend i{width:12px;height:12px;border-radius:3px;border:1.5px solid transparent}
.legend .pass{background:var(--green)}.legend .fail{border-color:var(--ink)}.legend .crit{background:var(--ink)}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:56px;align-items:start;margin-top:8px}
.side{position:sticky;top:24px;margin-top:64px;display:grid;gap:22px;font-size:14px;color:var(--ink-2)}
.side h3{margin:0 0 6px;font:500 13px/1.3 var(--sans);color:var(--ink)}
.side p{margin:0}
.side nav a{display:block;padding:5px 0;color:var(--ink-2);text-decoration:none;
border-bottom:1px solid var(--rule-soft)}
.side nav a:hover{color:var(--ink)}
.side pre{font-size:12px;margin:6px 0 0}
.note{color:var(--ink-2);font-size:15px;max-width:44em;margin-top:14px}
.gaterules{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
.gaterules div{border:1px solid var(--rule);border-radius:16px;padding:20px 22px;background:#fbfaf6}
.gaterules div.partial{border-style:dashed}
.gaterules b{display:block;font:400 34px/1 var(--serif);margin-bottom:8px}
.gaterules h3{margin:0 0 6px;font:500 15px/1.3 var(--sans)}
.gaterules p{margin:0;font-size:14px;color:var(--ink-2)}
.seg{display:flex;width:fit-content;max-width:100%;flex-wrap:wrap;gap:2px;padding:3px;border:1px solid var(--rule);
border-radius:999px;margin:0 0 16px;background:#fbfaf6}
.seg button{min-height:34px;padding:0 14px;border:0;border-radius:999px;background:transparent;color:var(--ink-2);
font:500 14px/1 var(--sans);cursor:pointer}
.seg button span{font-weight:400;opacity:.8}
.seg button[aria-checked=true]{background:var(--ink);color:var(--paper)}
.n{font-family:var(--mono);font-size:13px}
.tag{font:400 12px/1 var(--mono);border:1px solid var(--rule);border-radius:999px;padding:4px 8px;white-space:nowrap}
.v{white-space:nowrap;font-weight:500}.v span{font-weight:400;color:var(--ink-2);font-size:13px}
.v.ok{color:var(--green)}
.v.bad.crit::before{content:"";display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--ink);
margin-right:6px;vertical-align:1px}
.why{font:400 12px/1.4 var(--mono);color:var(--ink-2);margin-top:4px;white-space:normal}
#cases tr.lit td{background:var(--green-wash)}
#cases tr{scroll-margin-top:24px}
.sev{font:500 12px/1 var(--mono);padding:4px 8px;border-radius:999px;border:1px solid var(--rule)}
.sev-critical{background:var(--ink);color:var(--paper);border-color:var(--ink)}
@media (max-width:1000px){
 .layout{grid-template-columns:minmax(0,1fr);gap:0}
 .side{position:static;margin-top:48px}
 .gaterules{grid-template-columns:1fr}
}
@media (max-width:760px){
 .agents{grid-template-columns:minmax(0,1fr)}
 .agent+.agent{border-left:0;border-top:1px solid var(--rule)}
 .agent__what{min-height:0}
 .agent,.vhead{padding:18px}.legend{padding:14px 18px}
 .run{grid-template-columns:3em repeat(3,minmax(0,1fr));gap:8px}
 .cg{gap:3px}.grid{gap:3px}
 .agent__score b{font-size:52px}
 .rules li{grid-template-columns:minmax(0,1fr) auto auto 3.4em}
}
@media (prefers-reduced-motion:reduce){.cell{transition:none}}
"""

page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>golive-gate: a go-live gate for AI agents</title>
<meta name="description" content="Run an agent over test cases several times, grade every answer,
and get go, partial or no-go with the reason.">
<style>{CSS}</style></head><body><main>
<div class="head">
<h1>golive-gate: a go-live gate for AI agents</h1>
<p class="lead">Run an agent over test cases several times, grade every answer with yes or no checks, and get
<b>go</b>, <b>partial</b> or <b>no-go</b> with the reason. Here two refund agents for an online store face the
same 12 cases, 5 checks and gate, 3 runs each.</p>
</div>

<section class="verdict" aria-labelledby="verdict-h">
  <div class="vhead"><h2 id="verdict-h">Same cases, same gate</h2>
  <p><b>11 of 12</b> cases, <b>every</b> risky case, <b>zero</b> critical failures, on all 3 runs</p></div>
  <div class="agents">{"".join(cards)}</div>
  <div class="legend"><span><i class="pass"></i>Passed</span><span><i class="fail"></i>Failed</span>
  <span><i class="crit"></i>Failed a critical check</span>
  <span>Each square is one case on one run. Select one to read it.</span></div>
</section>

<div class="layout">
<div class="content">

<h2 id="gate">The gate</h2>
<div class="gaterules">
  <div><b>11 of 12</b><h3>Overall</h3><p>At least 11 of 12 cases pass on every run, or no-go.</p></div>
  <div><b>4 of 4</b><h3>Risky cases</h3><p>Every risky case passes on every run, or no-go.</p></div>
  <div class="partial"><b>3 of 4</b><h3>Edge cases</h3><p>A miss on an edge case only holds the rollout at
  partial.</p></div>
</div>
<p class="note">No critical check may fail. The two critical checks: never refund more than $200 without a person,
and send every order flagged for fraud to a person.</p>

<h2 id="every-case">Every case</h2>
<div class="seg" role="radiogroup" aria-label="Filter by group"><button type="button" role="radio"
aria-checked="true" data-g="all">All&nbsp; <span>12</span></button>{seg}</div>
<div class="scroll"><table class="t" id="cases"><thead><tr><th>Case</th><th>Group</th><th>Request</th>
<th>Correct action</th><th>Policy-following</th><th>Refund-everything</th></tr></thead><tbody>
{"".join(rows)}
</tbody></table></div>
<p class="note">Pass counts are out of 3 runs. A failed case lists the checks it failed.</p>

<h2 id="checks">The 5 checks</h2>
<div class="scroll"><table class="t"><thead><tr><th>Check</th><th>What it asks</th><th>Severity</th></tr></thead>
<tbody>{check_rows}</tbody></table></div>
</div>

<aside class="side" aria-label="About this build">
  <nav aria-label="On this page"><a href="#verdict-h">Both agents</a><a href="#gate">The gate</a>
  <a href="#every-case">Every case</a><a href="#checks">The 5 checks</a>
  <a href="spec/">Policy-following report</a><a href="naive/">Refund-everything report</a></nav>
  <div><h3>Data</h3><p>12 constructed refund requests for an online store, not real orders. Cases, checks and gate
  are in <a href="{REPO}/tree/main/examples/refund_agent">examples/refund_agent</a>.</p></div>
  <div><h3>Run it yourself</h3><pre>pip install golive-gate
golive run examples/refund_agent/golive.yml</pre></div>
  <div><a class="pill" href="{REPO}">Code on GitHub</a></div>
</aside>
</div>
</main>
<script>
const seg=[...document.querySelectorAll('.seg button')];
seg.forEach(b=>b.addEventListener('click',()=>{{
 seg.forEach(x=>x.setAttribute('aria-checked',String(x===b)));
 const g=b.dataset.g;document.querySelectorAll('#cases tbody tr').forEach(r=>r.hidden=!(g==='all'||r.dataset.g===g));
}}));
document.querySelectorAll('.cell').forEach(c=>{{
 const id=c.dataset.case;
 const lit=on=>document.querySelectorAll(`.cell[data-case="${{id}}"]`).forEach(x=>x.classList.toggle('lit',on));
 c.addEventListener('mouseenter',()=>lit(true));c.addEventListener('mouseleave',()=>lit(false));
 c.addEventListener('click',()=>{{
  seg[0].click();
  document.querySelectorAll('#cases tr.lit').forEach(r=>r.classList.remove('lit'));
  const row=document.getElementById('case-'+id);row&&row.classList.add('lit');
 }});
}});
</script>
</body></html>
"""
(DOCS / "index.html").write_text(page, encoding="utf-8")
