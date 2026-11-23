"""A single self-contained HTML page for a run: drop it in docs/ and GitHub Pages serves it.

No JavaScript and no external files: the styles are inline, and the fonts fall back to
Georgia, Helvetica and Menlo when the Field Guide fonts are not installed. Every case is
expandable to show each check's verdict and reason.
"""

from __future__ import annotations

import html
import json
from typing import Any

_LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}
# Line-art marks, not glyphs: a check for a case that passed every run, a cross otherwise.
_OK = '<svg viewBox="0 0 12 12" aria-label="passed"><path d="M2.6 6.3 5 8.6 9.4 3.6"/></svg>'
_BAD = '<svg viewBox="0 0 12 12" aria-label="failed"><path d="M3.4 3.4 8.6 8.6M8.6 3.4 3.4 8.6"/></svg>'


def render(data: dict[str, Any], title: str = "") -> str:
    """Render a results.json dict (see report.to_dict) as one HTML page."""
    e = html.escape
    decision = data["decision"]
    summary = data["summary"]
    gate = data["gate_result"]
    title = title or f"{data['gate']}: {_LABEL[decision]}"
    checks = {c["id"]: c for c in data["checks"]}

    reasons = "".join(f"<li>{e(r)}</li>" for r in gate["reasons"])
    by_run = "".join(
        f"<tr><td>{r['run']}</td><td>{r['passed']} of {r['total']}</td><td>{r['critical']}</td></tr>"
        for r in summary["by_run"]
    )
    rules = "".join(
        f"<tr><td>{e(r['name'])}</td><td>{r['run']}</td><td>{r['passed']} of {r['total']}</td>"
        f"<td>{r['required']}</td><td>{'held' if r['held'] else 'broke (' + e(r['on_fail']) + ')'}</td></tr>"
        for r in gate["rules"]
    )
    check_rows = "".join(
        f"<tr><td><code>{e(c['id'])}</code></td><td>{'critical' if c['critical'] else ''}</td>"
        f"<td>{e(c['text'])}</td></tr>"
        for c in data["checks"]
    )

    case_rows = []
    for case in data["cases"]:
        runs = case["runs"]
        passes = sum(r["passed"] for r in runs)
        ok = passes == len(runs)
        detail = []
        for r in runs:
            items = "".join(
                f"<li class='{v['result']}'><code>{e(cid)}</code> {v['result'].upper()}"
                f"{' (critical)' if checks.get(cid, {}).get('critical') else ''}"
                f"{': ' + e(v['reason']) if v['reason'] else ''}</li>"
                for cid, v in r["verdicts"].items()
            )
            err = f"<li class='fail'>agent error: {e(r['error'])}</li>" if r["error"] else ""
            output = e(json.dumps(r["output"], indent=1, ensure_ascii=False)) if r["output"] is not None else ""
            detail.append(
                f"<div class='run'><div class='runhead'>Run {r['run']}: {'pass' if r['passed'] else 'FAIL'}"
                f" · {r['latency_s'] * 1000:.0f} ms</div><ul>{err}{items}</ul>"
                f"<pre>{output}</pre></div>"
            )
        label = case["title"] or case["id"]
        case_rows.append(
            f"<details{'' if ok else ' open'}><summary><span class='mark {'ok' if ok else 'bad'}'>"
            f"{_OK if ok else _BAD}</span> <b>{e(label)}</b> <span class='muted'>{e(case['group'])} · "
            f"{passes} of {len(runs)} runs</span></summary>{''.join(detail)}</details>"
        )

    cost = (
        f"Agent cost ${summary['total_cost_usd']:.4f}, judge cost ${summary.get('total_judge_cost_usd', 0):.4f}, "
        f"mean latency {summary['mean_latency_s'] * 1000:.1f} ms per case."
    )
    agent = f"Agent <code>{e(data['agent'])}</code>, " if data.get("agent") else ""
    decision_class = {"go": "go", "partial": "partial", "no-go": "no-go"}[decision]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#f4f2ec">
<title>{e(title)}</title>
<style>{_CSS}</style></head><body><main>
<h1>{e(data["gate"])} <span class="decision {decision_class}">{_LABEL[decision]}</span></h1>
<p class="lead">{agent}{len(data["cases"])} cases, {data["runs"]} run(s). {e(cost)}</p>
<ul class="reasons">{reasons}</ul>
<h2>Pass counts by run</h2><div class="scroll"><table><tr><th>Run</th><th>Passed</th>
<th>Critical failures</th></tr>{by_run}</table></div>
<h2>Gate rules</h2><div class="scroll"><table><tr><th>Rule</th><th>Run</th><th>Passed</th><th>Needs</th>
<th>Result</th></tr>{rules}</table></div>
<h2>Cases</h2>{"".join(case_rows)}
<h2>Checks</h2><div class="scroll"><table>{check_rows}</table></div>
<footer class="muted">Made with <a href="https://github.com/pg2342-hub/golive-gate">golive-gate</a>.</footer>
</main></body></html>
"""


# Warm paper, warm ink, one evergreen accent. GO is the only green moment; NO-GO is solid ink.
_CSS = """
:root{--paper:#f4f2ec;--ink:#1b1a17;--ink-2:#57544c;--rule:rgb(27 26 23/.14);--green:#24513c;--wash:#dce6dc;
--serif:"Libre Caslon Display",Georgia,serif;--sans:"General Sans","Helvetica Neue",Arial,sans-serif;
--mono:"Red Hat Mono",ui-monospace,Menlo,monospace;color-scheme:light}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:400 16px/1.6 var(--sans)}
::selection{background:var(--wash)}a{color:var(--green);text-underline-offset:3px}
main{width:min(1080px,calc(100% - 64px));margin:0 auto;padding:0 0 64px}
h1{font:400 clamp(30px,3.6vw,46px)/1.15 var(--serif);letter-spacing:-.01em;margin:56px 0 18px;text-wrap:balance}
h2{display:inline-flex;align-items:center;min-height:44px;padding:0 20px;border:1px solid var(--ink);
border-radius:999px;font:400 21px/1.1 var(--serif);margin:56px 0 20px}
.lead,h1+p{font-size:18px;color:var(--ink-2);max-width:42em}.muted{color:var(--ink-2)}
.reasons{padding-left:20px;margin:16px 0 0}.reasons li{margin:6px 0}
.decision{display:inline-flex;align-items:center;min-height:32px;padding:0 14px;border-radius:999px;
font:500 15px/1 var(--mono);letter-spacing:.04em;vertical-align:.25em;margin-left:8px;border:1px solid var(--ink)}
.decision.go{background:var(--wash);border-color:var(--wash);color:var(--green)}
.decision.no-go{background:var(--ink);color:var(--paper)}.decision.partial{border-style:dashed}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:15px;font-variant-numeric:tabular-nums}
th{font:400 12.5px/1.4 var(--mono);letter-spacing:.02em;color:var(--ink-2);text-align:left;padding:10px 12px 10px 0;
border-bottom:1px solid var(--ink);white-space:nowrap}
td{text-align:left;border-bottom:1px solid var(--rule);padding:12px 12px 12px 0;vertical-align:top}
details{border-bottom:1px solid var(--rule);padding:12px 0}summary{cursor:pointer;list-style:none}
summary::-webkit-details-marker{display:none}
.mark{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:999px;
font-size:12px;margin-right:4px}.mark.ok{background:var(--wash);color:var(--green)}
.mark.bad{background:var(--ink);color:var(--paper)}
.mark svg{width:12px;height:12px}.mark path{fill:none;stroke:currentColor;stroke-width:1.5;stroke-linecap:round;
stroke-linejoin:round}summary b{font-weight:500}
.run{margin:10px 0 10px 28px}.runhead{font:400 12.5px/1.4 var(--mono);letter-spacing:.02em;color:var(--ink-2)}
ul{margin:4px 0;padding-left:18px}li.pass::marker{color:var(--green)}li.fail{font-weight:500}li.na{color:var(--ink-2)}
pre{font:400 12.5px/1.55 var(--mono);background:rgb(27 26 23/.045);border-radius:8px;padding:12px 14px;
overflow-x:auto;margin:6px 0;white-space:pre-wrap;word-break:break-word}
code{font-family:var(--mono);font-size:.86em}
footer{margin-top:64px;padding-top:18px;border-top:1px solid var(--rule);font:400 13px/1.5 var(--mono)}
@media (max-width:700px){main{width:calc(100% - 40px)}h1{margin-top:32px}h2{font-size:19px;margin-top:44px}
.lead,h1+p{font-size:16.5px}.run{margin-left:12px}}
"""
