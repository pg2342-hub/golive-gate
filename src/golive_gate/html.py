"""A single self-contained HTML page for a run: drop it in docs/ and GitHub Pages serves it.

No JavaScript framework, no external files besides the Inter font; every case is
expandable to show each check's verdict and reason.
"""

from __future__ import annotations

import html
import json
from typing import Any

_LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}


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
            f"{'✓' if ok else '✗'}</span> <b>{e(label)}</b> <span class='muted'>{e(case['group'])} · "
            f"{passes} of {len(runs)} runs</span></summary>{''.join(detail)}</details>"
        )

    cost = (
        f"Agent cost ${summary['total_cost_usd']:.4f}, judge cost ${summary.get('total_judge_cost_usd', 0):.4f}, "
        f"mean latency {summary['mean_latency_s'] * 1000:.1f} ms per case."
    )
    agent = f"Agent <code>{e(data['agent'])}</code>, " if data.get("agent") else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{{--fg:#111;--bg:#fff;--muted:#666;--line:#ddd;--soft:#f5f5f5}}
@media (prefers-color-scheme:dark){{:root{{--fg:#eee;--bg:#111;--muted:#999;--line:#333;--soft:#1b1b1b}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 Inter,system-ui,sans-serif}}main{{max-width:880px;margin:0 auto;padding:32px 16px 64px}}
h1{{font-size:28px;margin:0 0 4px}}h2{{font-size:18px;margin:32px 0 8px}}
.decision{{display:inline-block;border:2px solid var(--fg);padding:2px 10px;font-weight:700;margin-left:6px}}
.muted{{color:var(--muted)}}table{{border-collapse:collapse;width:100%;font-size:14px}}
td,th{{text-align:left;border-bottom:1px solid var(--line);padding:6px 8px;vertical-align:top}}
.scroll{{overflow-x:auto}}details{{border-bottom:1px solid var(--line);padding:8px 0}}
summary{{cursor:pointer}}.mark{{display:inline-block;width:18px;font-weight:700}}.bad{{color:var(--fg)}}
.run{{margin:8px 0 8px 22px}}.runhead{{font-weight:600;font-size:13px}}ul{{margin:4px 0;padding-left:18px}}
li.fail{{font-weight:600}}li.na{{color:var(--muted)}}pre{{background:var(--soft);padding:8px;overflow-x:auto;
font-size:12px;margin:4px 0}}code{{font-size:13px}}footer{{margin-top:40px;font-size:13px}}
</style></head><body><main>
<h1>{e(data["gate"])} <span class="decision">{_LABEL[decision]}</span></h1>
<p class="muted">{agent}{len(data["cases"])} cases, {data["runs"]} run(s). {e(cost)}</p>
<ul>{reasons}</ul>
<h2>Pass counts by run</h2><div class="scroll"><table><tr><th>Run</th><th>Passed</th>
<th>Critical failures</th></tr>{by_run}</table></div>
<h2>Gate rules</h2><div class="scroll"><table><tr><th>Rule</th><th>Run</th><th>Passed</th><th>Needs</th>
<th>Result</th></tr>{rules}</table></div>
<h2>Cases</h2>{"".join(case_rows)}
<h2>Checks</h2><div class="scroll"><table>{check_rows}</table></div>
<footer class="muted">Made with <a href="https://github.com/pg2342-hub/golive-gate">golive-gate</a>.</footer>
</main></body></html>
"""
