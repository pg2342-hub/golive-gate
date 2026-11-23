"""The booking grader's six error codes as golive-gate checks. E3 and E5 are critical."""

from agent import FSM
from booking import fsm as F
from booking.grader import grade

from golive_gate import CheckSet, Verdict

CODES = {
    "E1": "Right job type, business unit and campaign.",
    "E2": "Right fee, membership and billing contact.",
    "E3": "Never books outside the service area or in the wrong market.",
    "E4": "Right slot and priority, inside open capacity, no duplicate jobs.",
    "E5": "Hands off every call it should (safety, commercial, billing).",
    "E6": "Books clean calls instead of flagging or handing them off.",
}
CRITICAL = {"E3", "E5"}

checks = CheckSet()


def _errors(case, out):
    raw = dict(case.input, id=case.id, expected=case.expected)
    return grade(raw, out, F.fsm_for_case(FSM, case.input))


def _make(code):
    def check(case, out):
        found = [msg for c, msg in _errors(case, out) if c == code]
        return Verdict("fail", "; ".join(found)) if found else Verdict("pass")

    return check


for _code, _text in CODES.items():
    checks.check(_code, text=_text, critical=_code in CRITICAL)(_make(_code))
