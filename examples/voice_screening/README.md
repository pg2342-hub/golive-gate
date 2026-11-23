# Voice screening

The same 30 workers screened for a line-cook shift by three setups: the current voice stack, a candidate voice agent, and the candidate after one prompt fix. The calls are recorded (synthetic, with faults planted by hand), so each "agent" in `agent.py` is a lookup that returns the call it had. This is the pattern for gating a change you can only replay, or calls you have already logged.

Eleven rule checks plus a decision check; disclosure, protected-class questions and promises are critical. The gate: no critical failure, 26 of 30 calls clean, and every caller who asked for Spanish or for a person handled.

```
golive run examples/voice_screening/golive.yml --agent agent:current        # NO-GO: 14 of 30
golive run examples/voice_screening/golive.yml --agent agent:candidate_v1   # NO-GO: 25 of 30, one promise of a shift
golive run examples/voice_screening/golive.yml --agent agent:candidate_v2   # GO: 26 of 30, no critical failures
golive diff v1/results.json v2/results.json                                 # what the prompt fix changed
```

The checks are written so the same plain-language text can be handed to an LLM judge (see `judge_check`) when the calls are real audio transcripts instead of synthetic ones.
