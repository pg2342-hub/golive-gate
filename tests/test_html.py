from golive_gate import Gate, evaluate, run_eval
from golive_gate.html import render
from golive_gate.report import to_dict


def test_escapes_case_text(checks):
    from golive_gate import load_cases

    cases = load_cases([{"id": "x", "title": "<script>alert(1)</script>", "input": 1, "expected": 2}])
    result = run_eval(lambda x: x * 2, cases, checks)
    gate = Gate.from_dict({"rules": [{"min_pass": "all"}]})
    page = render(to_dict(result, gate, evaluate(gate, result)))
    assert "<script>alert" not in page and "&lt;script&gt;" in page
