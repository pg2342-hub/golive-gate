# Changelog

## Unreleased

Fixes from an independent review, all places where the gate could say go when it should not:

- A judge reply only counts when its last line is `VERDICT: PASS|FAIL|NA`. Before, a `VERDICT: PASS` anywhere in the reply, or `VERDICT: PASSABLE`, could pass a check.
- An agent crash counts as a critical failure when any check is critical, since the critical checks never ran.
- A case where every check said na no longer counts as a pass.
- `max_critical_failures` is a total across runs, not a per-run allowance.
- Rules that could quietly pass are config errors: an empty groups list, `min_pass` below 1 or not a whole number, both `min_pass` and `min_pass_rate`, a bad `max_critical_failures`.
- A check that returns something unreadable fails with a reason instead of stopping the run.
- `golive diff` compares pass rates, so a flaky regression (3 of 3 to 2 of 3) counts, and removing a case that used to pass counts as a regression.
- `--runs 0`, a group name with no cases, and a baseline that is not a results.json exit 3 before any agent call.
- The GitHub Action clears old reports first, so a failed run never reports a stale decision; `decision` is `error` when no results were written.
- Loading two projects whose folders share a name prefix keeps their modules apart.
- New `rude_agent` negative control for the LLM judge example, run in CI.

## 0.1.0 (2026-11-23)

- Cases from YAML, JSON, JSONL or Python lists, with groups, titles and tags.
- Checks as plain Python functions returning pass, fail or na; critical checks block the gate on one failure.
- Runner that calls any Python agent N times per case and records latency and cost.
- Gates written as YAML: overall and per-group minimums (count, "all" or a rate), critical-failure allowance, and rules that only hold rollout at partial. Every rule must hold on every run.
- `golive run` CLI with markdown and JSON reports and CI-friendly exit codes.
- LLM judge checks: one yes/no criterion per call, with the judge's reason and cost; `ClaudeJudge` built in, any callable works. Unreadable replies and refusals fail.
- HTTP agents (`agent: https://...`, headers from the environment) and agent-reported cost.
- `golive ablate`: which checks the gate depends on, from stored outputs.
- `golive diff` and `golive run --baseline`: regressions exit 1.
- Self-contained HTML report (`index.html`) for GitHub Pages, and a demo page for this repo.
- Composite GitHub Action with a `decision` output, tested on this repo.
- Release workflow for PyPI trusted publishing.
- Gate rules can cover several groups (`groups: [T1, T2]`).
- Projects that share module names (agent.py, checks.py) load side by side.
- Field-service booking and voice screening examples.
- Refund agent example: a policy-following agent that passes and a naive one the gate blocks.
