"""Ways to reach an agent other than a Python function."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Callable

from .runner import Response


def http_agent(url: str, headers: dict[str, str] | None = None, timeout: float = 60.0) -> Callable[[Any], Any]:
    """POST {"input": <case input>} as JSON to ``url``.

    The endpoint answers with JSON. If it has an "output" key, that is the output and an
    optional "cost_usd" is recorded; otherwise the whole body is the output.
    """
    base_headers = {"Content-Type": "application/json", "User-Agent": "golive-gate"}
    base_headers.update(headers or {})

    def call(case_input: Any) -> Any:
        body = json.dumps({"input": case_input}).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=base_headers, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if isinstance(data, dict) and "output" in data:
            return Response(data["output"], float(data.get("cost_usd", 0.0) or 0.0))
        return data

    call.__name__ = f"http_agent({url})"
    return call
