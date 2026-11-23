"""Command line: ``golive run golive.yml``.

Exit codes: 0 go, 1 no-go, 2 partial when --strict is set (partial exits 0 otherwise),
3 for a bad config.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__, report
from .config import load_project
from .gates import GO, NO_GO, PARTIAL, evaluate
from .runner import run_eval


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="golive", description="Run agent evals against a go-live gate.")
    parser.add_argument("--version", action="version", version=f"golive-gate {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run every case, grade it, and apply the gate")
    run.add_argument("config", nargs="?", default="golive.yml", help="path to golive.yml")
    run.add_argument("--agent", help="override the agent, as module:attribute")
    run.add_argument("--runs", type=int, help="override the number of runs")
    run.add_argument("--out", default=None, help="folder for report.md and results.json")
    run.add_argument("--strict", action="store_true", help="exit 2 on a partial result")

    args = parser.parse_args(argv)
    try:
        project = load_project(args.config, agent=args.agent, runs=args.runs)
    except (ValueError, TypeError, ImportError, AttributeError, FileNotFoundError) as exc:
        print(f"golive: config error: {exc}", file=sys.stderr)
        return 3

    result = run_eval(project.agent, project.cases, project.checks, runs=project.runs)
    outcome = evaluate(project.gate, result)
    out_dir = args.out or project.root / "reports"
    paths = report.write(out_dir, result, project.gate, outcome, agent=project.agent_ref)

    print(f"{project.gate.name}: {outcome.decision.upper()}")
    for r in outcome.reasons:
        print(f"  {r}")
    print(f"report: {paths['markdown']}")

    if outcome.decision == NO_GO:
        return 1
    if outcome.decision == PARTIAL and args.strict:
        return 2
    assert outcome.decision in (GO, PARTIAL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
