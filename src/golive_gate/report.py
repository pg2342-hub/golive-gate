"""Reports: a markdown summary for people and a JSON file for tools and demo pages."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import html
from .gates import Gate, GateResult
from .runner import RunResult

_LABEL = {"go": "GO", "partial": "PARTIAL", "no-go": "NO-GO"}


def to_dict(result: RunResult, gate: Gate, outcome: GateResult, agent: str = "") -> dict[str, Any]:
    return {
        "agent": agent,
        "gate": gate.name,
        "runs": result.runs,
        "decision": outcome.decision,
        "summary": _summary(result),
        "gate_result": outcome.to_dict(),
        "checks": [{"id": c.id, "text": c.text, "critical": c.critical} for c in result.checks],
        "cases": [
            {
                "id": case.id,
                "group": case.group,
                "title": case.title,
                "runs": [
                    {
                        "run": cr.run,
                        "passed": cr.passed,
                        "failed_checks": cr.failed_checks,
                        "error": cr.error,
                        "latency_s": round(cr.latency_s, 4),
                        "cost_usd": round(cr.cost_usd, 6),
                        "judge_cost_usd": round(cr.judge_cost_usd, 6),
                        "verdicts": {k: {"result": v.result, "reason": v.reason} for k, v in cr.verdicts.items()},
                        "output": _jsonable(cr.output),
                    }
                    for cr in result.for_case(case.id)
                ],
            }
            for case in result.cases
        ],
    }


def to_markdown(result: RunResult, gate: Gate, outcome: GateResult, agent: str = "") -> str:
    s = _summary(result)
    lines = [
        f"# {gate.name}: {_LABEL[outcome.decision]}",
        "",
        f"Agent `{agent or 'agent'}`, {len(result.cases)} cases, {result.runs} run(s).",
        "",
    ]
    lines += [f"- {r}" for r in outcome.reasons]
    lines += ["", "## Pass counts by run", "", "| Run | Passed | Critical failures |", "|---|---|---|"]
    for run in s["by_run"]:
        lines.append(f"| {run['run']} | {run['passed']} of {run['total']} | {run['critical']} |")
    lines += [
        "",
        f"Agent cost {s['total_cost_usd']:.4f} USD, judge cost {s['total_judge_cost_usd']:.4f} USD, "
        f"mean latency {s['mean_latency_s'] * 1000:.1f} ms per case.",
        "",
        "## Cases",
        "",
        "| Case | Group | Result | Failed checks |",
        "|---|---|---|---|",
    ]
    for case in result.cases:
        crs = result.for_case(case.id)
        passes = sum(cr.passed for cr in crs)
        failed = sorted({cid for cr in crs for cid in cr.failed_checks})
        errors = sorted({cr.error for cr in crs if cr.error})
        detail = ", ".join(failed + [f"error: {e}" for e in errors]) or ""
        label = case.title or case.id
        lines.append(f"| {label} | {case.group} | {passes} of {len(crs)} runs | {detail} |")
    lines += ["", "## Checks", "", "| Check | Critical | Text |", "|---|---|---|"]
    for c in result.checks:
        lines.append(f"| {c.id} | {'yes' if c.critical else ''} | {c.text} |")
    return "\n".join(lines) + "\n"


def write(out_dir: str | Path, result: RunResult, gate: Gate, outcome: GateResult, agent: str = "") -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    md = out / "report.md"
    js = out / "results.json"
    page = out / "index.html"
    data = to_dict(result, gate, outcome, agent)
    md.write_text(to_markdown(result, gate, outcome, agent), encoding="utf-8")
    js.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    page.write_text(html.render(data), encoding="utf-8")
    return {"markdown": md, "json": js, "html": page}


def _summary(result: RunResult) -> dict[str, Any]:
    by_run = []
    for run in range(1, result.runs + 1):
        rows = result.for_run(run)
        by_run.append(
            {
                "run": run,
                "passed": sum(r.passed for r in rows),
                "total": len(rows),
                "critical": len(result.critical_failures(run)),
            }
        )
    return {
        "by_run": by_run,
        "total_cost_usd": round(result.total_cost_usd, 6),
        "total_judge_cost_usd": round(result.total_judge_cost_usd, 6),
        "mean_latency_s": round(result.mean_latency_s, 6),
    }


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)
