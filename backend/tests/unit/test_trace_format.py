"""Unit tests for retrieval-track formatting helpers."""

from uuid import uuid4

from app.retrieval.hybrid import RetrievedChunk, RetrievalResult
from app.services.stream_events import trace_event
from app.services.trace_format import format_gate_detail, format_retrieval_detail


def test_trace_event_serialises_json_payload() -> None:
    event = trace_event("retrieve", "done", "Searching", "3 passages", {"chunk_count": 3})
    assert event["event"] == "trace"
    assert '"step": "retrieve"' in event["data"] or '"step":"retrieve"' in event["data"]


def test_format_retrieval_detail_includes_top_file() -> None:
    result = RetrievalResult(
        chunks=[
            RetrievedChunk(
                chunk_id=uuid4(),
                document_id=uuid4(),
                filename="vpn-guide.md",
                page=None,
                heading="Setup",
                text="x",
                score=0.81,
                char_start=0,
                char_end=1,
            )
        ],
        best_vector_similarity=0.81,
    )
    detail = format_retrieval_detail(result, hybrid_enabled=True, elapsed_ms=42)
    assert "hybrid" in detail
    assert "vpn-guide.md" in detail
    assert "0.81" in detail


def test_format_gate_detail_marks_pass_and_fail() -> None:
    assert "continue" in format_gate_detail(0.5, 0.3, True)
    assert "skip LLM" in format_gate_detail(0.1, 0.3, False)
