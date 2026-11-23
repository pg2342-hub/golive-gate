"""Eval cases: one input, what a correct answer looks like, and a group for gate rules."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Case:
    id: str
    input: Any
    expected: Any = None
    group: str = "default"
    title: str = ""
    tags: tuple = ()
    meta: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict) -> Case:
        if "id" not in raw:
            raise ValueError(f"case is missing an id: {raw!r}")
        if "input" not in raw:
            raise ValueError(f"case {raw['id']!r} is missing an input")
        known = {"id", "input", "expected", "group", "title", "tags"}
        return cls(
            id=str(raw["id"]),
            input=raw["input"],
            expected=raw.get("expected"),
            group=str(raw.get("group", "default")),
            title=str(raw.get("title", "")),
            tags=tuple(raw.get("tags", ())),
            meta={k: v for k, v in raw.items() if k not in known},
        )


def load_cases(source: str | Path | Iterable[dict]) -> list[Case]:
    """Load cases from a .yml/.yaml, .json or .jsonl file, or from a list of dicts."""
    if isinstance(source, (str, Path)):
        raw = _read(Path(source))
    else:
        raw = list(source)
    cases = [c if isinstance(c, Case) else Case.from_dict(c) for c in raw]
    seen: set[str] = set()
    for c in cases:
        if c.id in seen:
            raise ValueError(f"duplicate case id {c.id!r}")
        seen.add(c.id)
    if not cases:
        raise ValueError("no cases loaded")
    return cases


def _read(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if suffix == ".json":
        data = json.loads(text)
    elif suffix in (".yml", ".yaml"):
        data = yaml.safe_load(text)
    else:
        raise ValueError(f"unsupported case file type: {path.suffix}")
    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]
    if not isinstance(data, list):
        raise ValueError(f"{path} must hold a list of cases (or a 'cases' key)")
    return data
