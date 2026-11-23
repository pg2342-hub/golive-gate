"""golive.yml: where the cases, checks, agent and gate live.

    cases: cases.yml            # .yml, .json or .jsonl, relative to this file
    checks: checks:checks       # module:attribute holding a CheckSet
    agent: agent:spec_agent     # module:attribute called with each case's input, or an http(s) URL
    agent_headers:              # optional, for an http agent; ${VARS} are read from the environment
      Authorization: Bearer ${AGENT_TOKEN}
    gate: gate.yml              # a file, or the gate written inline as a mapping
    runs: 3

Modules are imported from the folder that holds golive.yml.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .agents import http_agent
from .cases import Case, load_cases
from .checks import CheckSet
from .gates import Gate


@dataclass
class Project:
    root: Path
    cases: list[Case]
    checks: CheckSet
    agent: Any
    agent_ref: str
    gate: Gate
    runs: int


def load_project(path: str | Path, agent: str | None = None, runs: int | None = None) -> Project:
    path = Path(path).resolve()
    root = path.parent
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("cases", "checks", "agent", "gate"):
        if key not in raw and not (key == "agent" and agent):
            raise ValueError(f"{path.name} is missing '{key}'")

    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    checks = resolve(raw["checks"])
    if not isinstance(checks, CheckSet):
        raise TypeError(f"'checks' must point to a CheckSet, got {type(checks).__name__}")
    agent_ref = agent or raw["agent"]
    if agent_ref.startswith(("http://", "https://")):
        headers = {k: os.path.expandvars(str(v)) for k, v in (raw.get("agent_headers") or {}).items()}
        agent_fn = http_agent(agent_ref, headers=headers)
    else:
        agent_fn = resolve(agent_ref)
    if not callable(agent_fn):
        raise TypeError(f"agent {agent_ref!r} is not callable")

    gate_raw = raw["gate"]
    gate = Gate.from_dict(gate_raw) if isinstance(gate_raw, dict) else Gate.load(root / gate_raw)

    return Project(
        root=root,
        cases=load_cases(root / raw["cases"]),
        checks=checks,
        agent=agent_fn,
        agent_ref=agent_ref,
        gate=gate,
        runs=int(runs if runs is not None else raw.get("runs", 1)),
    )


def resolve(ref: str) -> Any:
    """Import 'package.module:attribute'."""
    if ":" not in ref:
        raise ValueError(f"expected 'module:attribute', got {ref!r}")
    module_name, attr = ref.split(":", 1)
    module = importlib.import_module(module_name)
    obj: Any = module
    for part in attr.split("."):
        obj = getattr(obj, part)
    return obj
