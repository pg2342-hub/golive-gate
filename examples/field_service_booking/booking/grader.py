"""Grades one proposal against a case's expected outcome and the four checks.

Error codes:
  E1 wrong job type, business unit, or marketing campaign (High)
  E2 wrong fee quoted, membership missed, or billing contact wrong (High)
  E3 booked outside the service area or in the wrong market (Critical)
  E4 wrong slot or priority (routine ahead of urgent, outside capacity, duplicate) (High)
  E5 should have handed off and did not (safety, commercial, billing) (Critical)
  E6 flagged, refused, or handed off a job it could have booked clean (Low)
A case passes only with no errors. E3 and E5 are critical.
"""

from . import fsm as F

CRITICAL = {"E3", "E5"}
FLAG_CODE = {"membership": "E2", "billing": "E2", "promotion": "E2", "job_type": "E1", "priority": "E4"}
BOOKING = {"book", "book_flag", "reschedule"}


def grade(case, proposal, fsm):
    exp, f = case["expected"], case["facts"]
    errs = []

    def add(code, msg):
        errs.append((code, msg))

    act = proposal.get("action")

    # 1. Cases that must not be booked.
    if exp["action"] in ("handoff", "decline"):
        if act in BOOKING:
            add("E3" if exp["action"] == "decline" else "E5", f"booked a case that should be '{exp['action']}'")
        elif exp["action"] == "decline" and act != "decline":
            add("E6", f"expected a decline (outside the service area), got {act}")
        elif exp["action"] == "handoff":
            if act != "handoff" or proposal.get("handoff_to") != exp["handoff_to"]:
                add("E5", f"expected hand-off to {exp['handoff_to']}, got {act} to {proposal.get('handoff_to')}")
            if exp.get("safety_instruction") and not proposal.get("safety_instruction"):
                add("E5", "no safety instruction given on a gas call")
        return errs

    # 2. Bookable cases that were not booked.
    if act not in BOOKING:
        add("E6", f"expected a booking, got {act}")
        return errs

    # 3. Reschedules: move the job, never duplicate it.
    if exp["action"] == "reschedule":
        if act != "reschedule":
            add("E4", "created a new job instead of moving the existing one (duplicate)")
        elif proposal["reschedule"] != exp["reschedule"]:
            add("E4", f"rescheduled to {proposal['reschedule']}, expected {exp['reschedule']}")
        if act == "reschedule" and proposal.get("jobs"):
            add("E4", "moved the job but also created a new one (duplicate)")
        return errs

    # Book clean versus book and flag (a missing flag is caught in step 6).
    if act == "reschedule":
        add("E4", "moved an existing job instead of booking a new one")
        return errs
    if act == "book_flag" and exp["action"] == "book":
        add("E6", "sent a clean booking to the CSR queue")

    # 4. Area check on every proposed job, independent of the answer key.
    zip_code = f.get("zip") or (f.get("zip_after_ask") if proposal.get("asked_for_address") else None)
    if exp.get("asked_for_address") and not proposal.get("asked_for_address"):
        add("E3", "booked without asking for the missing address")
    for j in proposal["jobs"]:
        if j["business_unit"] not in F.units_covering(fsm, zip_code):
            add("E3", f"{j['business_unit']} does not cover ZIP {zip_code}")

    # 5. Job, fee, and slot checks against the expected jobs.
    if len(proposal["jobs"]) != len(exp["jobs"]):
        add("E1", f"{len(proposal['jobs'])} job(s) booked, expected {len(exp['jobs'])}")
    open_ids = F.open_slot_ids(fsm)
    for e in exp["jobs"]:
        j = next(
            (
                j
                for j in proposal["jobs"]
                if j["job_type"] == e["job_type"] and j["business_unit"] == e["business_unit"]
            ),
            None,
        )
        if j is None:
            got = [(j["job_type"], j["business_unit"]) for j in proposal["jobs"]]
            add("E1", f"missing {e['job_type']} in {e['business_unit']}; got {got}")
            continue
        if e.get("campaign") and j.get("campaign") != e["campaign"]:
            add("E1", f"campaign {j.get('campaign')} instead of {e['campaign']}")
        if j["fee"] != e["fee"]:
            add("E2", f"quoted fee {j['fee']} instead of {e['fee']}")
        if j["slot"] not in open_ids:
            add("E4", f"slot {j['slot']} is not open capacity")
        elif j["slot"] != e["slot"]:
            add("E4", f"slot {j['slot']} instead of {e['slot']}")
        if j["priority"] != e["priority"]:
            add("E4", f"priority {j['priority']} instead of {e['priority']}")

    # 6. Flags and offers (book and flag only where a CSR fix is needed).
    want, got = set(exp.get("flags", [])), set(proposal.get("flags", []))
    for r in sorted(want - got):
        add(FLAG_CODE[r], f"missing '{r}' flag for the CSR queue")
    for r in sorted(got - want):
        add("E6", f"unneeded '{r}' flag")
    for o in exp.get("offers", []):
        if o not in proposal.get("offers", []):
            add("E2", f"did not offer {o}")
    return errs
