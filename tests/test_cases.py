import json

import pytest

from golive_gate import Case, load_cases


def test_load_yaml_with_cases_key(tmp_path):
    p = tmp_path / "c.yml"
    p.write_text("cases:\n  - {id: 1, input: hi, expected: HI, group: g, owner: ops}\n")
    (case,) = load_cases(p)
    assert case == Case(id="1", input="hi", expected="HI", group="g", meta={"owner": "ops"})


def test_load_json_and_jsonl(tmp_path):
    rows = [{"id": "a", "input": 1}, {"id": "b", "input": 2}]
    (tmp_path / "c.json").write_text(json.dumps(rows))
    (tmp_path / "c.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n\n")
    assert [c.id for c in load_cases(tmp_path / "c.json")] == ["a", "b"]
    assert [c.group for c in load_cases(tmp_path / "c.jsonl")] == ["default", "default"]


@pytest.mark.parametrize(
    "rows, message",
    [
        ([{"input": 1}], "missing an id"),
        ([{"id": "x"}], "missing an input"),
        ([{"id": "x", "input": 1}, {"id": "x", "input": 2}], "duplicate"),
        ([], "no cases"),
    ],
)
def test_bad_cases_are_rejected(rows, message):
    with pytest.raises(ValueError, match=message):
        load_cases(rows)


def test_unknown_file_type(tmp_path):
    p = tmp_path / "c.csv"
    p.write_text("id,input\n")
    with pytest.raises(ValueError, match="unsupported"):
        load_cases(p)
