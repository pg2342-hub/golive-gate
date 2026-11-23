"""Agents under test. Each agent maps (case, fsm) -> a booking proposal (a dict).

Proposal shape:
  action: "book" | "book_flag" | "reschedule" | "handoff" | "decline"
  jobs: [{job_type, business_unit, fee, slot, priority, campaign}]
  reschedule: {job_id, slot} | None
  flags: [reason], offers: [str], handoff_to: str | None,
  safety_instruction: bool, asked_for_address: bool, log: [str]

NaiveAgent books the way a plain "always book" agent would. SpecAgent is a reference
implementation of the four booking checks (job, fee, area, slot) plus the trade-off rule:
book and flag what a CSR can fix before the technician leaves; hand off what cannot be fixed later.
SpecAgent reads structured facts, so it shows the checks can be written as code and that the
grader scores a correct policy 25 of 25.
"""

from . import fsm as F


def _proposal(**kw):
    p = {
        "action": "book",
        "jobs": [],
        "reschedule": None,
        "flags": [],
        "offers": [],
        "handoff_to": None,
        "safety_instruction": False,
        "asked_for_address": False,
        "log": [],
    }
    p.update(kw)
    return p


class NaiveAgent:
    name = "naive"

    def propose(self, case, fsm):
        f = case["facts"]
        eq = f.get("said_equipment") or "furnace"
        eqd = fsm["equipment"].get(eq) or fsm["equipment"]["ac"]
        req = f.get("request") if f.get("request") in ("repair", "maintenance", "estimate") else "repair"
        job_type = eqd.get(req) or eqd.get("repair") or next(iter(v for k, v in eqd.items() if k != "trade"))
        bu = next(
            b for b, u in fsm["business_units"].items() if u["trade"] == eqd["trade"] and u["market"] == "St. Louis"
        )
        cust = F.find_customer(fsm, f["phone"])
        member = bool(cust and any(loc_["membership"] for loc_ in cust["locations"]))
        fee = None if req == "estimate" else (0 if req == "maintenance" and member else (49 if member else 95))
        slots = F.open_slot_ids(fsm, None if f.get("after_hours") else "routine")
        return _proposal(
            jobs=[
                {
                    "job_type": job_type,
                    "business_unit": bu,
                    "fee": fee,
                    "slot": slots[0],
                    "priority": "Normal",
                    "campaign": None,
                }
            ],
            log=["booked first open window"],
        )


class SpecAgent:
    """disable: any of {"job", "fee", "area", "slot", "handoff"} to switch a check off (used by ablation.py)."""

    name = "spec"

    def __init__(self, disable=()):
        self.off = set(disable)

    def propose(self, case, fsm):
        f = case["facts"]
        log = []
        # Hand-offs that cannot be fixed after the fact run first, from day one.
        if "handoff" not in self.off and f.get("request") == "billing_dispute":
            return _proposal(action="handoff", handoff_to="CSR", log=["billing dispute: not a booking"])
        if "handoff" not in self.off and f.get("safety") == "gas_smell":
            return _proposal(
                action="handoff",
                handoff_to="CSR",
                safety_instruction=True,
                log=["gas smell: told caller to leave and call the gas utility or 911; live hand-off"],
            )
        if "handoff" not in self.off and f.get("property_type") == "commercial":
            return _proposal(action="handoff", handoff_to="COMM", log=["commercial property: route to commercial team"])

        # Area check (ask once for the address if it is missing).
        zip_code, asked = f.get("zip"), False
        if not zip_code and "area" not in self.off:
            asked, zip_code = True, f.get("zip_after_ask")
            log.append("asked once for the service address")
        if not zip_code and "area" not in self.off:
            return _proposal(
                action="handoff", handoff_to="CSR", asked_for_address=True, log=log + ["no address after one ask"]
            )
        if "area" not in self.off and not F.units_covering(fsm, zip_code):
            return _proposal(
                action="decline",
                asked_for_address=asked,
                log=log + [f"ZIP {zip_code} is not on any business unit's list; told caller"],
            )

        # Reschedule: move the existing job, never create a second one.
        if f.get("request") == "reschedule" and "slot" not in self.off:
            cust = F.find_customer(fsm, f["phone"])
            job = next(j for j in cust.get("open_jobs", []) if j["id"] == f["existing_job_id"])
            slot = (
                f.get("accepts_slot")
                if f.get("accepts_slot") in F.open_slot_ids(fsm, "routine")
                else F.open_slot_ids(fsm, "routine")[0]
            )
            return _proposal(
                action="reschedule",
                reschedule={"job_id": job["id"], "slot": slot},
                log=[f"moved {job['id']} to {slot}"],
            )

        # Fee check: membership by phone, then by service address.
        flags, offers = [], []
        cust = F.find_customer(fsm, f["phone"])
        loc = None
        if cust:
            loc = next((loc_ for loc_ in cust["locations"] if loc_["zip"] == zip_code), None)
        if loc is None:
            matches = F.locations_by_address(fsm, f.get("street"), zip_code)
            if len(matches) == 1:
                cust, loc = matches[0]
                log.append("membership found by service address")
        mem = (loc or {}).get("membership")
        status = mem["status"] if mem else None
        if "fee" in self.off:  # phone-only lookup, any membership counts as active
            cust = F.find_customer(fsm, f["phone"])
            status = "active" if cust and any(loc_["membership"] for loc_ in cust["locations"]) else None
        if status == "expired":
            flags.append("membership")
            offers.append("renewal")
            log.append("membership expired: quoted standard fee, offered renewal, CSR to confirm")

        # Job check (by symptom, not by the word the caller used), one job per problem.
        symptoms = [f.get("symptom")] + ([f["second_symptom"]] if f.get("second_symptom") else [])
        if "job" in self.off:  # trust the caller's word, one job per call
            symptoms = [next((k for k, v in fsm["symptoms"].items() if v == f.get("said_equipment")), f.get("symptom"))]
        if (
            f.get("request") == "reschedule"
        ):  # ablation only (slot check off): books the open job's problem as a new job
            symptoms = ["no_cooling"]
        slot_ids = F.open_slot_ids(fsm, None if "slot" in self.off else "routine")
        slot = f.get("accepts_slot") if f.get("accepts_slot") in slot_ids else slot_ids[0]
        if f.get("wants_same_day") and "D0-EVE" not in F.open_slot_ids(fsm):
            flags.append("priority")
            log.append("no same-day capacity: earliest window booked, dispatcher to review")
        jobs = []
        for s in symptoms:
            if (
                s not in fsm["symptoms"]
            ):  # no usable symptom (only reachable with a check off): fall back to the caller's word
                s = next((k for k, v in fsm["symptoms"].items() if v == f.get("said_equipment")), "no_cooling")
            eq = fsm["symptoms"][s]
            eqd = fsm["equipment"][eq]
            req = f["request"] if f["request"] in ("repair", "maintenance", "estimate") else "repair"
            job_type = eqd.get(req) or eqd["repair"]
            if eq == "heating_unknown":
                flags.append("job_type")
                log.append("system type unknown: booked a heating diagnostic")
            covering = F.units_covering(fsm, zip_code, trade=eqd["trade"])
            bu = (
                covering[0]
                if covering
                else next(b for b, u in fsm["business_units"].items() if u["trade"] == eqd["trade"])
            )
            if req == "estimate":
                fee = None
            elif req == "maintenance" and status == "active":
                fee = fsm["fees"]["plan_tuneup"]
            elif status == "active":
                fee = fsm["fees"]["member_service"]
            else:
                fee = fsm["fees"]["standard_service"]
            jobs.append(
                {
                    "job_type": job_type,
                    "business_unit": bu,
                    "fee": fee,
                    "slot": slot,
                    "priority": "Normal",
                    "campaign": f.get("lead_source"),
                }
            )
        if f.get("payer_differs"):
            flags.append("billing")
            log.append("payer is not the occupant: CSR to set billing contact")
        if f.get("promo_claimed"):
            flags.append("promotion")
            log.append("unverified promotion: quoted standard fee, CSR to confirm")
        return _proposal(
            action="book_flag" if flags else "book",
            jobs=jobs,
            flags=flags,
            offers=offers,
            asked_for_address=asked,
            log=log,
        )


AGENTS = {"naive": NaiveAgent, "spec": SpecAgent}
