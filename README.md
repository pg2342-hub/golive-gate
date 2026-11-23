# golive-gate

[![CI](https://github.com/pg2342-hub/golive-gate/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/golive-gate/actions/workflows/ci.yml)

Demo page: https://pranavgudise.dev/golive-gate/ (two refund agents on the same cases and gate: one goes live, one is blocked, with every case and check; no install needed)

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

## Examples

| Example | What it shows |
|---|---|
| [refund_agent](examples/refund_agent) | The smallest complete project: 12 cases, five checks (two critical), a gate with a partial rule, and an optional LLM judge check |
| [field_service_booking](examples/field_service_booking) | 25 booking calls for a home-services company, a full grader with six error codes, and tiered gate rules (T1-T2 15 of 16, every T3 and T4) |
| [voice_screening](examples/voice_screening) | Recorded calls from three setups graded as-is: the candidate is blocked by one promise of a shift, then passes after a prompt fix, and `golive diff` shows what changed |

## Install

```
pip install golive-gate
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

A check returns `True`/`False`, `"pass"`/`"fail"`/`"na"`, `None` (na), a `(result, reason)` pair, or a `Verdict`. A check that raises, or returns anything else, counts as a failure, with the reason kept.

A case passes when no check fails and at least one check applied: a case where every check said na was never tested, so it does not count as a pass. If the agent crashes on a case, that case fails, and when the project has any critical check the crash also counts as a critical failure, since the critical checks never got to run.

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

The decision is **no-go** if critical failures exceed the allowance or any `no-go` rule breaks on any run, **partial** if only `partial` rules break, and **go** otherwise. `max_critical_failures` is a total across all runs: the same failure on 3 runs counts 3 times. Rules are checked when the project loads, so a typo in a group name, `min_pass: 0.9` (use `min_pass_rate`), or setting both `min_pass` and `min_pass_rate` is a config error, never a gate that quietly passes.

## Output

`golive run` writes three files to `reports/` next to `golive.yml`, or to `--out`:

- `report.md`, for people and pull request summaries
- `results.json`, for tools, diffs and dashboards
- `index.html`, one self-contained page with every case and check verdict. Put it in `docs/` and GitHub Pages serves it as a demo (`scripts/build_demo.sh` builds this repo's).

| Exit code | Meaning |
|---|---|
| 0 | go (or partial, unless `--strict`) |
| 1 | no-go, or a regression against `--baseline` |
| 2 | partial with `--strict` |
| 3 | config error (bad golive.yml or gate, unknown group, `--runs 0`, a baseline that is not a results.json) |

So a CI step that runs `golive run` fails the build when the agent is not ready. This repo's own CI does exactly that with the examples: each reference agent must pass, and each weak agent must be blocked with a no-go decision in results.json (not just exit 1, which a config error could also cause in another setup).

## GitHub Action

```yaml
- uses: actions/checkout@v4
- id: gate
  uses: pg2342-hub/golive-gate@main
  with:
    config: evals/golive.yml
    baseline: evals/baseline/results.json   # optional: fail on any regression
    extras: claude                          # optional: for LLM judge checks
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
- run: echo "decision was ${{ steps.gate.outputs.decision }}"
```

The job fails on no-go (or on partial with `strict: "true"`), the markdown report lands on the job summary page, and the `decision` output is go, partial or no-go. This repo tests the action on itself in `.github/workflows/action-selftest.yml`.

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

The judge must end its reply with one line, `VERDICT: PASS`, `VERDICT: FAIL` or `VERDICT: NA`, then an optional reason. Only the last line counts, so a verdict quoted mid-reply or an echoed rubric cannot pass a check. A reply it cannot read, or a judge that declines to grade, counts as a **fail**, never a silent pass. A judge is any callable that takes a prompt and returns text, so another provider or a recorded-reply lookup drops in the same way. Judge cost is reported separately from agent cost. See `examples/refund_agent/golive.judge.yml`. CI runs it with a real model against two agents: the reference agent (the judge passes its declines) and `rude_agent`, a negative control that makes every right decision and mentions the refund window, so every rule check passes, but blames the customer. The judge has to fail it for the gate to say no-go.

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

Cases are compared by how many runs they passed. A case that passes on fewer runs than before regressed, so a case that was 3 of 3 and is now 2 of 3 counts. Removing a case that used to pass on every run also counts, so a regression cannot be hidden by deleting the case that shows it. Any regression, or a worse gate decision, exits 1, so a prompt or model change that breaks a case that used to work fails CI even if the overall gate still holds.

## Use it from Python

```python
from golive_gate import Gate, Response, evaluate, load_cases, run_eval

result = run_eval(my_agent, load_cases("cases.yml"), checks, runs=3)
outcome = evaluate(Gate.load("gate.yml"), result)
print(outcome.decision, outcome.reasons)
```

An agent can return `Response(output, cost_usd=...)` to have cost recorded; latency is always measured.

## Roadmap

- More worked examples: field-service booking, text-message ordering, voice screening

## License

MIT
