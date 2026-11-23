"""Recorded calls as agents: each setup "answers" a case with the call it actually had.

This is how you gate a change you can only replay, or calls you already logged: the
agent is a lookup, and every check runs on the recorded transcript.
"""

import json
from pathlib import Path

CALLS = json.loads((Path(__file__).parent / "data" / "recorded_calls.json").read_text())["calls"]


def _setup(name):
    def agent(case_input):
        return CALLS[name][case_input["worker"]]

    agent.__name__ = name
    return agent


current = _setup("current")
candidate_v1 = _setup("candidate_v1")
candidate_v2 = _setup("candidate_v2")
