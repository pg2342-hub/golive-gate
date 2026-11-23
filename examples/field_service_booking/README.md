# Field-service booking

A booking agent for a home-services company (HVAC, plumbing, electrical) answers calls and texts and either books a job, books it and flags it for a person to fix, reschedules, hands off, or declines. 25 constructed calls in four tiers:

- **T1-T2** routine bookings (16)
- **T3** judgment calls such as missing addresses or storm-day capacity (5)
- **T4** calls that must go to a person: gas smells, commercial jobs, billing disputes (4)

The grader in `booking/grader.py` scores six error codes, wired up as six checks in `checks.py`. E3 (outside the service area) and E5 (missed hand-off) are critical. The gate: 24 of 25 on every run, T1-T2 at 15 of 16, every T3 and T4 call, and no critical error.

```
golive run examples/field_service_booking/golive.yml                            # reference agent: GO
golive run examples/field_service_booking/golive.yml --agent agent:naive_agent  # "always book": NO-GO
golive ablate examples/field_service_booking/golive.yml --agent agent:naive_agent --runs 1
```

All data, including the mock field service system in `data/fsm.json`, is constructed.
