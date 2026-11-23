import pytest

from golive_gate import FAIL, NA, PASS, Case, Check, CheckSet, Verdict

CASE = Case(id="1", input=1)


@pytest.mark.parametrize(
    "returned, expected",
    [
        (True, PASS),
        (False, FAIL),
        (None, NA),
        ("na", NA),
        (("fail", "why"), FAIL),
        (Verdict(PASS, "ok"), PASS),
    ],
)
def test_return_values_become_verdicts(returned, expected):
    assert Check("c", lambda case, out: returned).run(CASE, None).result == expected


def test_crashing_check_fails_with_reason():
    v = Check("c", lambda case, out: 1 / 0).run(CASE, None)
    assert v.result == FAIL and "ZeroDivisionError" in v.reason


@pytest.mark.parametrize("raw", ["maybe", 2, -1, 0.5, ["pass"], {"result": "pass"}])
def test_unreadable_check_result_fails_instead_of_crashing(raw):
    v = Check("c", lambda case, out: raw).run(CASE, None)
    assert v.result == FAIL and "not pass, fail or na" in v.reason


@pytest.mark.parametrize("raw, result", [(1, PASS), (0, FAIL), (" PASS ", PASS), ("Na", NA), (None, NA)])
def test_check_result_coercion(raw, result):
    assert Check("c", lambda case, out: raw).run(CASE, None).result == result


def test_checkset_decorator_order_and_without(checks):
    assert [c.id for c in checks] == ["doubles", "not_negative_for_positive"]
    assert checks["not_negative_for_positive"].critical
    assert [c.id for c in checks.without("doubles")] == ["not_negative_for_positive"]
    with pytest.raises(KeyError):
        checks.without("nope")


def test_duplicate_check_id():
    cs = CheckSet([Check("a", lambda c, o: True)])
    with pytest.raises(ValueError):
        cs.add(Check("a", lambda c, o: True))


def test_docstring_becomes_text():
    cs = CheckSet()

    @cs.check("a")
    def a(case, out):
        """Says what it checks."""
        return True

    assert cs["a"].text == "Says what it checks."
