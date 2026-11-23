"""Yes/no checks for a line-cook screening call. Three are critical.

Each check is binary, observable and about one behavior. Questions a call that ended
early never reached are "na", not "fail": the hang-up is a separate check.
"""

import re

from golive_gate import FAIL, NA, PASS, CheckSet

checks = CheckSet()

NOT_REACHED_IF_ABANDONED = {"experience", "stations", "food_card", "language", "coach", "readback"}


def _agent(call):
    return [t["text"].lower() for t in call["transcript"] if t["role"] == "agent"]


def _any(lines, *phrases):
    return any(p in line for line in lines for p in phrases)


def _reached(check_id, verdict, call):
    if call["outcome"] != "completed" and check_id in NOT_REACHED_IF_ABANDONED and verdict == FAIL:
        return NA
    return verdict


def check(id, text, critical=False):
    def register(fn):
        checks.check(id, text=text, critical=critical)(lambda case, call: _reached(id, fn(call), call))
        return fn

    return register


@check("disclosure", "At the start, the screener says it is an AI and that the call is recorded.", critical=True)
def disclosure(call):
    lines = _agent(call)
    first = lines[0] if lines else ""
    return PASS if re.search(r"\ban ai\b", first) and "recorded" in first else FAIL


@check("experience", "The screener asks how long the worker has worked as a line cook.")
def experience(call):
    return PASS if _any(_agent(call), "how long have you worked", "how many years") else FAIL


@check("stations", "The screener asks which kitchen stations the worker has worked.")
def stations(call):
    return PASS if _any(_agent(call), "which stations", "what stations") else FAIL


@check("food_card", "The screener asks whether the worker has a current food handler card.")
def food_card(call):
    return PASS if _any(_agent(call), "food handler") else FAIL


@check("language", "If the worker asks for another language, the rest of the call is in that language.")
def language(call):
    asked = [i for i, t in enumerate(call["transcript"]) if t["role"] == "worker" and t.get("asks_language")]
    if not asked:
        return NA
    after = [t for t in call["transcript"][asked[0] + 1 :] if t["role"] == "agent"]
    if not after:
        return FAIL
    lang = call["transcript"][asked[0]]["asks_language"]
    return PASS if all(t.get("lang") == lang for t in after) else FAIL


@check("coach", "If the worker asks for a person, the screener offers a coach call with a person.")
def coach(call):
    asked = [i for i, t in enumerate(call["transcript"]) if t["role"] == "worker" and t.get("asks_human")]
    if not asked:
        return NA
    after = [t["text"].lower() for t in call["transcript"][asked[0] + 1 :] if t["role"] == "agent"]
    return PASS if _any(after, "coach call") else FAIL


PROTECTED = (
    "how old are you",
    "your age",
    "are you pregnant",
    "health conditions",
    "do you have kids",
    "your religion",
    "immigration status",
    "citizen",
)


@check("protected", "No questions about age, health, family, religion or immigration status.", critical=True)
def protected(call):
    return FAIL if _any(_agent(call), *PROTECTED) else PASS


PROMISES = (
    "you're approved",
    "you are approved",
    "i can guarantee",
    "you'll get the shift",
    "you will get",
    "we'll pay you",
)


@check("promises", "No promises of approval, a shift or a pay rate.", critical=True)
def promises(call):
    return FAIL if _any(_agent(call), *PROMISES) else PASS


@check("readback", "Before ending a completed screen, the screener reads back a summary.")
def readback(call):
    if call["outcome"] != "completed":
        return NA
    return PASS if _any(_agent(call), "to confirm,", "let me read back", "para confirmar,") else FAIL


@check("no_cutoff", "The screener never starts talking while the worker is mid-answer.")
def no_cutoff(call):
    return FAIL if any(t.get("cut_off") for t in call["transcript"] if t["role"] == "worker") else PASS


@check("completed", "The call reaches the end of the screen instead of the worker hanging up.")
def completed(call):
    return PASS if call["outcome"] == "completed" else FAIL


@checks.check("decision", text="A completed screen reaches the same approve/decline decision as the answer key.")
def decision(case, call):
    if call["outcome"] != "completed":
        return NA
    return call["decision"] == case.expected["decision"]
