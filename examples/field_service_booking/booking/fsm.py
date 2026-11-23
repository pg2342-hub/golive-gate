"""Mock field service system: business units, ZIP coverage, customers and capacity. All data is constructed."""

import copy
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def load_fsm():
    return json.loads((DATA / "fsm.json").read_text())


def load_cases():
    return json.loads((DATA / "cases.json").read_text())


def fsm_for_case(fsm, case):
    """Apply per-case capacity overrides (e.g. a storm day that fills tomorrow's windows)."""
    f = copy.deepcopy(fsm)
    remove = set(case.get("fsm_overrides", {}).get("remove_slots", []))
    f["slots"] = [s for s in f["slots"] if s["id"] not in remove]
    return f


def units_covering(fsm, zip_code, trade=None, residential_only=True):
    out = []
    for bu, u in fsm["business_units"].items():
        if residential_only and u.get("residential_booking") is False:
            continue
        if trade and u["trade"] != trade:
            continue
        if zip_code and zip_code in u["zips"]:
            out.append(bu)
    return out


def find_customer(fsm, phone):
    for c in fsm["customers"]:
        if phone in c["phones"]:
            return c
    return None


def locations_by_address(fsm, street, zip_code):
    """Match a service address (street + ZIP) to a customer location."""
    if not street:
        return []
    return [
        (c, loc)
        for c in fsm["customers"]
        for loc in c["locations"]
        if loc["zip"] == zip_code and loc.get("street", "").lower() == street.lower()
    ]


def open_slot_ids(fsm, kind=None):
    return [s["id"] for s in fsm["slots"] if kind is None or s["kind"] == kind]
