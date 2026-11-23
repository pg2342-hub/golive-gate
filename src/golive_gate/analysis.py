"""Ablation and regression diffs, both computed from results that already exist."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .gates import Gate, evaluate
from .runner import RunResult


@dataclass
class AblationRow:
    check: str
    critical: bool
    decision: str  # the gate decision if this check did not exist
    cases_caught: list[str]  # cases that fail with the check and pass without it

    @property
    def load_bearing(self) -> bool:
        return bool(self.cases_caught)


def ablate(gate: Gate, result: RunResult) -> tuple[str, list[AblationRow]]:
    """Switch off each check in turn and see what the gate would have said.

    No agent or judge calls are made: the stored outputs are re-graded without one check.
    A check that catches no case on its own is either redundant or untested by this case set.
    """
    baseline = evaluate(gate, result).decision
    rows = []
    for check in result.checks:
        reduced = result.without_checks(check.id)
        caught = sorted(
            {full.case_id for full, red in zip(result.case_runs, reduced.case_runs) if not full.passed and red.passed}
        )
        rows.append(AblationRow(check.id, check.critical, evaluate(gate, reduced).decision, caught))
    return baseline, rows


def ablation_markdown(baseline: str, rows: list[AblationRow]) -> str:
    lines = [
        f"# Ablation (gate with every check: {baseline.upper()})",
        "",
        "| Check switched off | Critical | Gate would say | Cases only this check catches |",
        "|---|---|---|---|",
    ]
    for r in rows:
        caught = ", ".join(r.cases_caught) or "none"
        lines.append(f"| {r.check} | {'yes' if r.critical else ''} | {r.decision.upper()} | {caught} |")
    return "\n".join(lines) + "\n"


@dataclass
class Diff:
    before: str
    after: str
    regressed: list[str]  # passes on fewer runs than before
    fixed: list[str]  # passes on more runs than before
    added: list[str]
    removed: list[str]
    removed_passing: list[str] = field(default_factory=list)  # removed cases that passed on every run

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressed) or bool(self.removed_passing) or _rank(self.after) < _rank(self.before)


def diff(before: dict[str, Any], after: dict[str, Any]) -> Diff:
    """Compare two results.json files by each case's share of passing runs.

    A case that passes on fewer runs than before regressed, so a flaky case that now
    always fails counts. Removing a case that used to pass on every run also counts,
    so a regression cannot be hidden by deleting the case that shows it.
    """
    check_results(before, "before")
    check_results(after, "after")
    b, a = _pass_rates(before), _pass_rates(after)
    removed = sorted(set(b) - set(a))
    return Diff(
        before=before["decision"],
        after=after["decision"],
        regressed=sorted(k for k in a if k in b and a[k] < b[k]),
        fixed=sorted(k for k in a if k in b and a[k] > b[k]),
        added=sorted(set(a) - set(b)),
        removed=removed,
        removed_passing=[k for k in removed if b[k] == 1.0],
    )


def diff_markdown(d: Diff) -> str:
    lines = [f"# Regression diff: {d.before.upper()} -> {d.after.upper()}", ""]
    for label, items in (
        ("Regressed (passes on fewer runs than before)", d.regressed),
        ("Fixed (passes on more runs than before)", d.fixed),
        ("New cases", d.added),
        ("Removed cases", d.removed),
        ("Removed cases that used to pass (counts as a regression)", d.removed_passing),
    ):
        lines.append(f"- {label}: {', '.join(items) if items else 'none'}")
    return "\n".join(lines) + "\n"


def check_results(results: dict[str, Any], label: str = "results") -> None:
    """Raise ValueError if this is not a results.json written by golive run."""
    if not isinstance(results, dict) or results.get("decision") not in ("go", "partial", "no-go"):
        raise ValueError(f"{label} is not a golive results.json (no go, partial or no-go decision)")
    try:
        _pass_rates(results)
    except (KeyError, TypeError) as exc:
        raise ValueError(f"{label} is not a golive results.json (bad cases list: {exc})") from exc


def _pass_rates(results: dict[str, Any]) -> dict[str, float]:
    return {c["id"]: sum(r["passed"] for r in c["runs"]) / max(len(c["runs"]), 1) for c in results["cases"]}


def _rank(decision: str) -> int:
    return {"no-go": 0, "partial": 1, "go": 2}[decision]
