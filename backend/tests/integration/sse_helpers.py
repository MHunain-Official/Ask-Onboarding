"""Tiny helper for parsing an `EventSourceResponse` stream in tests. Not a
test module itself — real SSE wire-format parsing is `lib/sse.ts` on the
frontend; this just needs to be good enough to assert event order here.
"""

import json

import httpx

CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def read_sse_events(response: httpx.Response) -> list[tuple[str, dict[str, object]]]:
    """Collect every `(event, data)` pair from a streamed SSE response."""
    events: list[tuple[str, dict[str, object]]] = []
    current_event: str | None = None
    for line in response.iter_lines():
        if line.startswith("event:"):
            current_event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            payload = line.removeprefix("data:").strip()
            assert current_event is not None
            events.append((current_event, json.loads(payload) if payload else {}))
    return events
