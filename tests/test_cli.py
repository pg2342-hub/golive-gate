import json
from pathlib import Path

import pytest

from golive_gate.cli import main

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "refund_agent" / "golive.yml"


def test_example_spec_agent_is_go(tmp_path, capsys):
    assert main(["run", str(EXAMPLE), "--out", str(tmp_path)]) == 0
    assert "GO" in capsys.readouterr().out
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["decision"] == "go" and data["runs"] == 3 and len(data["cases"]) == 12
    assert (tmp_path / "report.md").read_text().startswith("# Refund agent go-live gate: GO")


def test_example_naive_agent_is_no_go(tmp_path):
    assert main(["run", str(EXAMPLE), "--agent", "agent:naive_agent", "--runs", "1", "--out", str(tmp_path)]) == 1
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["decision"] == "no-go"
    assert {f["check"] for f in data["gate_result"]["critical_failures"]["1"]} == {
        "auto_limit",
        "fraud_handoff",
    }


def test_partial_exit_codes(tmp_path):
    (tmp_path / "cases.yml").write_text("- {id: a, group: g, input: 1}\n- {id: b, group: h, input: 2}\n")
    (tmp_path / "proj_checks.py").write_text(
        "from golive_gate import CheckSet\nchecks = CheckSet()\n"
        "@checks.check('odd')\ndef odd(case, out):\n    return out % 2 == 1\n"
        "def agent(x):\n    return x\n"
    )
    (tmp_path / "golive.yml").write_text(
        "cases: cases.yml\nchecks: proj_checks:checks\nagent: proj_checks:agent\n"
        "gate: {rules: [{min_pass: 1}, {group: h, min_pass: all, on_fail: partial}]}\n"
    )
    out = tmp_path / "out"
    assert main(["run", str(tmp_path / "golive.yml"), "--out", str(out)]) == 0
    assert main(["run", str(tmp_path / "golive.yml"), "--out", str(out), "--strict"]) == 2


@pytest.mark.parametrize(
    "config, message",
    [
        ("cases: c.yml\n", "missing 'checks'"),
        ("cases: c.yml\nchecks: nomodule:checks\nagent: a:b\ngate: {rules: [{min_pass: 1}]}\n", "nomodule"),
    ],
)
def test_config_errors_exit_3(tmp_path, capsys, config, message):
    (tmp_path / "golive.yml").write_text(config)
    assert main(["run", str(tmp_path / "golive.yml")]) == 3
    assert message in capsys.readouterr().err
