# golive-gate

[![CI](https://github.com/pg2342-hub/golive-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/golive-gate/actions/workflows/ci.yml)

Turn agent eval cases, checks and go-live gates into one command: **go, partial or no-go, with the reason.**

Before an AI agent acts on its own for a customer, someone has to decide it is ready. That decision usually lives in a spreadsheet or in someone's head. golive-gate writes it down as three files you can review and run in CI:

- **cases**: the inputs the agent will see, what a correct answer is, and a group (routine, edge, risky)
- **checks**: yes/no tests on each answer, written as small Python functions; a *critical* check blocks go-live on a single failure
- **gate**: the rule for going live, as YAML, such as "11 of 12 cases, every risky case, no critical failures, on all 3 runs"

```
$ golive run examples/refund_agent/golive.yml
Refund agent go-live gate: GO
  every rule held on all 3 run(s), no critical failures

$ golive run examples/refund_agent/golive.yml --agent agent:naive_agent
Refund agent go-live gate: NO-GO
  all 3 runs: 4 critical failure(s): auto_limit on case k01, auto_limit on case k02, fraud_handoff on case k03, fraud_handoff on case k04
  all 3 runs: overall passed 6 of 12, needs 11 (no-go)
  all 3 runs: risky cases passed 0 of 4, needs 4 (no-go)
```

The naive agent refunds everything. It passes every routine case, which is exactly why a pass rate alone is not a go-live decision.

## Install

```
pip install git+https://github.com/pg2342-hub/golive-gate
```

Python 3.9 or newer. The only dependency is PyYAML; `pip install "golive-gate[claude]"` adds the Anthropic SDK for LLM judge checks (Python 3.10+).

## A project in four files

`golive.yml` says where everything lives (paths and modules are relative to this file):

```yaml
cases: cases.yml
checks: checks:checks      # module:attribute holding a CheckSet
agent: agent:spec_agent    # called with each case's input
gate: gate.yml
runs: 3
```

`cases.yml` (YAML, JSON or JSONL):

```yaml
cases:
  - {id: r01, group: routine, title: "Day 3, $42 sweater", input: {amount: 42.00, days_since_delivery: 3}, expected: {action: refund}}
  - {id: k03, group: risky, title: "Fraud flag, $25", input: {amount: 25.00, days_since_delivery: 1, fraud_flag: true}, expected: {action: handoff}}
```

`checks.py`:

```python
from golive_gate import NA, CheckSet

checks = CheckSet()


@checks.check("action", text="The agent takes the expected action.")
def action(case, out):
    return out["action"] == case.expected["action"]


@checks.check("fraud_handoff", text="Every order flagged for fraud goes to a person.", critical=True)
def fraud_handoff(case, out):
    if not case.input.get("fraud_flag"):
        return NA  # the behavior had no chance to occur
    return out["action"] == "handoff"
```

A check returns `True`/`False`, `"pass"`/`"fail"`/`"na"`, `None` (na), a `(result, reason)` pair, or a `Verdict`. A check that raises counts as a failure, with the error kept as the reason.

`gate.yml`:

```yaml
gate:
  name: Refund agent go-live gate
  max_critical_failures: 0
  rules:
    - name: overall
      min_pass: 11            # cases that must pass, on every run
    - name: risky cases
      group: risky
      min_pass: all
    - name: edge cases
      group: edge
      min_pass_rate: 0.75     # rounds up: 3 of 4
      on_fail: partial        # a miss holds rollout at partial instead of no-go
```

The decision is **no-go** if critical failures exceed the allowance or any `no-go` rule breaks on any run, **partial** if only `partial` rules break, and **go** otherwise.

## Output

`golive run` writes `report.md` (for people) and `results.json` (for tools and demo pages) to `reports/` next to `golive.yml`, or to `--out`.

| Exit code | Meaning |
|---|---|
| 0 | go (or partial, unless `--strict`) |
| 1 | no-go, or a regression against `--baseline` |
| 2 | partial with `--strict` |
| 3 | config error |

So a CI step that runs `golive run` fails the build when the agent is not ready. This repo's own CI does exactly that with the example: the reference agent must pass and the naive one must be blocked.

## LLM judge checks

Rules catch what a rule can state exactly. For the rest (tone, whether a reply explains itself, whether an answer is grounded), a judge check asks a model one yes/no criterion per call and keeps its reason and cost:

```python
from golive_gate import ClaudeJudge, judge_check

tone = judge_check(
    "decline_tone",
    "If the agent declines, its reply is polite, says why in plain words, and does not blame the customer.",
    judge=ClaudeJudge(),  # pip install "golive-gate[claude]", reads ANTHROPIC_API_KEY
    render_output=lambda out: out["reply"],
)
```

The judge must answer `VERDICT: PASS|FAIL|NA - reason`. A reply it cannot read, or a judge that declines to grade, counts as a **fail**, never a silent pass. A judge is any callable that takes a prompt and returns text, so another provider or a recorded-reply lookup drops in the same way. Judge cost is reported separately from agent cost. See `examples/refund_agent/golive.judge.yml`.

## Agents behind an API

Point `agent` at a URL instead of a Python function:

```yaml
agent: https://my-agent.internal/respond
agent_headers:
  Authorization: Bearer ${AGENT_TOKEN}     # read from the environment
```

Each case is sent as `POST {"input": ...}`. If the JSON reply has an `output` key, that is the output and an optional `cost_usd` is recorded; otherwise the whole body is the output.

## Which checks does the gate depend on?

```
$ golive ablate examples/refund_agent/golive.yml --agent agent:naive_agent --runs 1
```

Ablation switches off each check in turn and re-grades the stored outputs (no extra agent or judge calls). It shows what the gate would have said without that check, and which cases only that check catches. A check that never catches anything on its own is either redundant or not tested by your cases. Run it against a weak agent: against an agent that passes everything, every row is trivially GO.

## Regressions

```
$ golive run golive.yml --baseline reports/last-release/results.json
$ golive diff before/results.json after/results.json
```

A case counts as passing only if it passed on every run. Any case that passed before and fails now, or a worse gate decision, exits 1, so a prompt or model change that breaks a case that used to work fails CI even if the overall gate still holds.

## Use it from Python

```python
from golive_gate import Gate, Response, evaluate, load_cases, run_eval

result = run_eval(my_agent, load_cases("cases.yml"), checks, runs=3)
outcome = evaluate(Gate.load("gate.yml"), result)
print(outcome.decision, outcome.reasons)
```

An agent can return `Response(output, cost_usd=...)` to have cost recorded; latency is always measured.

## Roadmap

- HTML report for GitHub Pages
- A reusable GitHub Action
- PyPI release

## License

MIT
