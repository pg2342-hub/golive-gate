import pytest

from golive_gate import CheckSet, load_cases


@pytest.fixture
def cases():
    return load_cases(
        [
            {"id": "a", "group": "easy", "input": 2, "expected": 4},
            {"id": "b", "group": "easy", "input": 3, "expected": 6},
            {"id": "c", "group": "hard", "input": -1, "expected": -2},
            {"id": "d", "group": "hard", "input": 0, "expected": 0},
        ]
    )


@pytest.fixture
def checks():
    cs = CheckSet()

    @cs.check("doubles", text="Output is twice the input.")
    def doubles(case, out):
        return out == case.expected

    @cs.check("not_negative_for_positive", text="Positive in, positive out.", critical=True)
    def sign(case, out):
        if case.input <= 0:
            return "na"
        return out > 0

    return cs
