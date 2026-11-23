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


def test_bad_verdict_string_is_rejected():
    with pytest.raises(ValueError):
        Check("c", lambda case, out: "maybe").run(CASE, None)


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
