# Changelog

## 0.1.0.dev0 (unreleased)

- Cases from YAML, JSON, JSONL or Python lists, with groups, titles and tags.
- Checks as plain Python functions returning pass, fail or na; critical checks block the gate on one failure.
- Runner that calls any Python agent N times per case and records latency and cost.
- Gates written as YAML: overall and per-group minimums (count, "all" or a rate), critical-failure allowance, and rules that only hold rollout at partial. Every rule must hold on every run.
- `golive run` CLI with markdown and JSON reports and CI-friendly exit codes.
- Refund agent example: a policy-following agent that passes and a naive one the gate blocks.
