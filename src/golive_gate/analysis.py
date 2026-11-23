"""Ablation and regression diffs, both computed from results that already exist."""

from __future__ import annotations

from dataclasses import dataclass
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
    regressed: list[str]  # passed on every run before, not now
    fixed: list[str]  # failed before, passes on every run now
    added: list[str]
    removed: list[str]

    @property
    def has_regressions(self) -> bool:
        return bool(self.regressed) or _rank(self.after) < _rank(self.before)


def diff(before: dict[str, Any], after: dict[str, Any]) -> Diff:
    """Compare two results.json files. A case counts as passing only if it passed on every run."""
    b, a = _passes(before), _passes(after)
    return Diff(
        before=before["decision"],
        after=after["decision"],
        regressed=sorted(k for k in a if k in b and b[k] and not a[k]),
        fixed=sorted(k for k in a if k in b and not b[k] and a[k]),
        added=sorted(set(a) - set(b)),
        removed=sorted(set(b) - set(a)),
    )


def diff_markdown(d: Diff) -> str:
    lines = [f"# Regression diff: {d.before.upper()} -> {d.after.upper()}", ""]
    for label, items in (
        ("Regressed (passed before, fails now)", d.regressed),
        ("Fixed (failed before, passes now)", d.fixed),
        ("New cases", d.added),
        ("Removed cases", d.removed),
    ):
        lines.append(f"- {label}: {', '.join(items) if items else 'none'}")
    return "\n".join(lines) + "\n"


def _passes(results: dict[str, Any]) -> dict[str, bool]:
    return {c["id"]: all(r["passed"] for r in c["runs"]) for c in results["cases"]}


def _rank(decision: str) -> int:
    return {"no-go": 0, "partial": 1, "go": 2}[decision]
