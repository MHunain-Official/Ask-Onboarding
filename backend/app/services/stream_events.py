"""Builds the SSE event dicts for `POST /api/chat/stream` (AGENTS.md §5.4).

`sse-starlette` passes each dict straight into `ServerSentEvent(**dict)`,
which only `str()`s a dict `data` value rather than JSON-encoding it — so
every payload here is serialised to a JSON string ourselves first.
"""

import json
from typing import Any

SseEvent = dict[str, str]


def meta_event(request_id: str, conversation_id: str) -> SseEvent:
    return _event("meta", {"request_id": request_id, "conversation_id": conversation_id})


def token_event(text: str) -> SseEvent:
    return _event("token", {"text": text})


def citations_event(items: list[dict[str, Any]]) -> SseEvent:
    return _event("citations", {"items": items})


def ticket_offer_event(suggested_title: str, question: str) -> SseEvent:
    return _event("ticket_offer", {"suggested_title": suggested_title, "question": question})


def done_event(message_id: str, status: str) -> SseEvent:
    return _event("done", {"message_id": message_id, "status": status})


def error_event(code: str, message: str, request_id: str) -> SseEvent:
    return _event("error", {"code": code, "message": message, "request_id": request_id})


def _event(name: str, payload: dict[str, Any]) -> SseEvent:
    return {"event": name, "data": json.dumps(payload)}
