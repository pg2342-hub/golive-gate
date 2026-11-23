"""Adapters: golive-gate calls agent(case.input); the booking agents want (case, fsm)."""

from booking import fsm as F
from booking.agents import NaiveAgent, SpecAgent

FSM = F.load_fsm()


def _run(agent, case_input):
    return agent.propose(case_input, F.fsm_for_case(FSM, case_input))


def spec_agent(case_input):
    return _run(SpecAgent(), case_input)


def naive_agent(case_input):
    return _run(NaiveAgent(), case_input)
