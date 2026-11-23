"""Checks: yes/no tests on one agent output. Each returns pass, fail or na."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Callable

PASS, FAIL, NA = "pass", "fail", "na"
VERDICTS = (PASS, FAIL, NA)


@dataclass(frozen=True)
class Verdict:
    result: str
    reason: str = ""
    cost_usd: float = 0.0  # what grading cost, e.g. an LLM judge call

    def __post_init__(self) -> None:
        if self.result not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}, got {self.result!r}")


@dataclass(frozen=True)
class Check:
    """One yes/no criterion.

    ``fn(case, output)`` returns "pass", "fail", "na", a bool, or a Verdict.
    ``critical`` means a single failure anywhere blocks the gate.
    """

    id: str
    fn: Callable[[Any, Any], Any]
    text: str = ""
    critical: bool = False

    def run(self, case: Any, output: Any) -> Verdict:
        try:
            raw = self.fn(case, output)
        except Exception as exc:  # a crashing check is a failed check, with the reason kept
            return Verdict(FAIL, f"check raised {type(exc).__name__}: {exc}")
        return _coerce(raw)


def _coerce(raw: Any) -> Verdict:
    if isinstance(raw, Verdict):
        return raw
    if isinstance(raw, bool):
        return Verdict(PASS if raw else FAIL)
    if raw is None:
        return Verdict(NA)
    if isinstance(raw, tuple) and len(raw) == 2:
        return Verdict(str(raw[0]), str(raw[1]))
    return Verdict(str(raw))


class CheckSet:
    """A named, ordered collection of checks, filled with the ``@checks.check`` decorator."""

    def __init__(self, checks: Iterable[Check] = ()) -> None:
        self._checks: dict[str, Check] = {}
        for c in checks:
            self.add(c)

    def add(self, c: Check) -> None:
        if c.id in self._checks:
            raise ValueError(f"duplicate check id {c.id!r}")
        self._checks[c.id] = c

    def check(self, id: str, text: str = "", critical: bool = False):
        def register(fn: Callable) -> Callable:
            self.add(Check(id=id, fn=fn, text=text or (fn.__doc__ or "").strip(), critical=critical))
            return fn

        return register

    def without(self, *ids: str) -> CheckSet:
        missing = set(ids) - set(self._checks)
        if missing:
            raise KeyError(f"unknown check ids: {sorted(missing)}")
        return CheckSet(c for c in self if c.id not in ids)

    def __iter__(self):
        return iter(self._checks.values())

    def __len__(self) -> int:
        return len(self._checks)

    def __getitem__(self, id: str) -> Check:
        return self._checks[id]
