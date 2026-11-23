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


def test_ablate_and_baseline(tmp_path, capsys):
    assert main(["ablate", str(EXAMPLE), "--agent", "agent:naive_agent", "--runs", "1", "--out", str(tmp_path)]) == 0
    assert "| auto_limit | yes | NO-GO |" in (tmp_path / "ablation.md").read_text()

    good = tmp_path / "good"
    assert main(["run", str(EXAMPLE), "--runs", "1", "--out", str(good)]) == 0
    base = str(good / "results.json")
    # Same agent against its own baseline: no regression.
    assert main(["run", str(EXAMPLE), "--runs", "1", "--out", str(tmp_path / "again"), "--baseline", base]) == 0
    bad = tmp_path / "bad"
    assert main(["run", str(EXAMPLE), "--agent", "agent:naive_agent", "--runs", "1", "--out", str(bad)]) == 1
    capsys.readouterr()
    assert main(["diff", base, str(bad / "results.json")]) == 1
    assert "k03" in capsys.readouterr().out
    assert main(["diff", base, base]) == 0
    assert main(["diff", base, str(tmp_path / "missing.json")]) == 3


def test_html_page_written(tmp_path):
    assert main(["run", str(EXAMPLE), "--agent", "agent:naive_agent", "--runs", "1", "--out", str(tmp_path)]) == 1
    page = (tmp_path / "index.html").read_text()
    assert page.startswith("<!doctype html>")
    assert "NO-GO" in page and "Fraud flag, $25" in page and "fraud_handoff" in page
    assert "<script" not in page


BOOKING = Path(__file__).resolve().parents[1] / "examples" / "field_service_booking" / "golive.yml"


def test_booking_example_matches_original_harness(tmp_path):
    # Same results as the standalone harness it was ported from: reference 25/25, naive 5/25, 7 critical.
    assert main(["run", str(BOOKING), "--runs", "1", "--out", str(tmp_path / "s")]) == 0
    assert main(["run", str(BOOKING), "--agent", "agent:naive_agent", "--runs", "1", "--out", str(tmp_path / "n")]) == 1
    naive = json.loads((tmp_path / "n" / "results.json").read_text())
    assert naive["summary"]["by_run"] == [{"run": 1, "passed": 5, "total": 25, "critical": 7}]
    # And the refund example still loads its own agent.py afterwards.
    assert main(["run", str(EXAMPLE), "--runs", "1", "--out", str(tmp_path / "r")]) == 0


VOICE = Path(__file__).resolve().parents[1] / "examples" / "voice_screening" / "golive.yml"


@pytest.mark.parametrize(
    "agent, code, passed, critical",
    [("agent:current", 1, 14, 1), ("agent:candidate_v1", 1, 25, 1), ("agent:candidate_v2", 0, 26, 0)],
)
def test_voice_example(tmp_path, agent, code, passed, critical):
    assert main(["run", str(VOICE), "--agent", agent, "--out", str(tmp_path)]) == code
    data = json.loads((tmp_path / "results.json").read_text())
    assert data["summary"]["by_run"] == [{"run": 1, "passed": passed, "total": 30, "critical": critical}]
