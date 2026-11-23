"""Command line.

    golive run [golive.yml]          run every case, grade it, apply the gate
    golive ablate [golive.yml]       which checks the gate actually depends on
    golive diff BEFORE AFTER         compare two results.json files

Exit codes for run: 0 go, 1 no-go, 2 partial when --strict is set (partial exits 0
otherwise), 3 config error. With --baseline, a regression against the baseline also
exits 1. diff exits 1 when anything regressed.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, report
from .analysis import ablate, ablation_markdown, diff, diff_markdown
from .config import load_project
from .gates import NO_GO, PARTIAL, evaluate
from .runner import run_eval

CONFIG_ERRORS = (ValueError, TypeError, ImportError, AttributeError, FileNotFoundError, KeyError)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golive", description="Run agent evals against a go-live gate.")
    parser.add_argument("--version", action="version", version=f"golive-gate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run every case, grade it, and apply the gate")
    _project_args(run)
    run.add_argument("--out", default=None, help="folder for report.md and results.json")
    run.add_argument("--strict", action="store_true", help="exit 2 on a partial result")
    run.add_argument("--baseline", help="an earlier results.json to diff against; a regression exits 1")

    abl = sub.add_parser("ablate", help="switch off each check in turn and show what the gate would say")
    _project_args(abl)
    abl.add_argument("--out", default=None, help="folder for ablation.md")

    dif = sub.add_parser("diff", help="compare two results.json files")
    dif.add_argument("before")
    dif.add_argument("after")

    args = parser.parse_args(argv)
    if args.command == "diff":
        return _diff(args)

    try:
        project = load_project(args.config, agent=args.agent, runs=args.runs)
        baseline = json.loads(Path(args.baseline).read_text()) if getattr(args, "baseline", None) else None
    except CONFIG_ERRORS as exc:
        print(f"golive: config error: {exc}", file=sys.stderr)
        return 3

    result = run_eval(project.agent, project.cases, project.checks, runs=project.runs)
    out_dir = Path(args.out) if args.out else project.root / "reports"

    if args.command == "ablate":
        decision, rows = ablate(project.gate, result)
        text = ablation_markdown(decision, rows)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ablation.md").write_text(text, encoding="utf-8")
        print(text, end="")
        return 0

    outcome = evaluate(project.gate, result)
    paths = report.write(out_dir, result, project.gate, outcome, agent=project.agent_ref)
    print(f"{project.gate.name}: {outcome.decision.upper()}")
    for r in outcome.reasons:
        print(f"  {r}")
    print(f"report: {paths['markdown']}")

    regressed = False
    if baseline is not None:
        d = diff(baseline, report.to_dict(result, project.gate, outcome, agent=project.agent_ref))
        print(diff_markdown(d), end="")
        regressed = d.has_regressions

    if outcome.decision == NO_GO or regressed:
        return 1
    if outcome.decision == PARTIAL and args.strict:
        return 2
    return 0


def _project_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("config", nargs="?", default="golive.yml", help="path to golive.yml")
    p.add_argument("--agent", help="override the agent: module:attribute or an http(s) URL")
    p.add_argument("--runs", type=int, help="override the number of runs")


def _diff(args: argparse.Namespace) -> int:
    try:
        before = json.loads(Path(args.before).read_text())
        after = json.loads(Path(args.after).read_text())
        d = diff(before, after)
    except (OSError, ValueError, KeyError) as exc:
        print(f"golive: cannot diff: {exc}", file=sys.stderr)
        return 3
    print(diff_markdown(d), end="")
    return 1 if d.has_regressions else 0


if __name__ == "__main__":
    raise SystemExit(main())
