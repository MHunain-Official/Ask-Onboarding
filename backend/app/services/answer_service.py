"""Top-level chat orchestration (AGENTS.md §5.4): router → document RAG
or a short-circuit mode (small-talk / history / explain-simpler).

SSE events: `meta`, `trace`, `token`, `citations`, `ticket_offer`, `done`,
`error` (§5.4 + retrieval-track breadcrumbs).
"""

from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.base import LlmClient
from app.models import Conversation, MessageRole, User
from app.schemas import ChatRequest
from app.security_hardening import matches_injection_pattern
from app.services.audit_service import record_audit_event
from app.services.conversation_service import (
    load_history_messages,
    load_or_create_conversation,
    persist_message,
)
from app.services.query_router import route_question
from app.services.rag_document_flow import run_document_rag
from app.services.stream_events import (
    SseEvent,
    done_event,
    error_event,
    meta_event,
    token_event,
    trace_event,
)


def stream_chat_answer(
    *,
    db: Session,
    user: User,
    request_id: str,
    body: ChatRequest,
    settings: Settings,
    llm_client: LlmClient,
    cancel_check: Callable[[], bool] | None = None,
) -> Generator[SseEvent, None, None]:
    conversation = load_or_create_conversation(db, user, body.conversation_id)
    yield meta_event(request_id, str(conversation.id))
    yield trace_event(
        "receive",
        "done",
        "Received question",
        "Session authenticated · request accepted",
    )

    # Cheap, log-only prompt-injection flagger (§5.8).
    if matches_injection_pattern(body.question):
        record_audit_event(
            db,
            event_type="injection_pattern_flagged",
            request_id=request_id,
            user_id=user.id,
            details={"source": "question", "question": body.question[:500]},
        )
        yield trace_event(
            "injection_flag",
            "done",
            "Injection pattern noted",
            "Logged for admin review — answer path unchanged",
        )

    yield trace_event("route", "running", "Routing the question")
    decision = route_question(body.question, settings.max_question_chars)
    if decision.action == "reject":
        yield trace_event("route", "failed", "Routing the question", decision.message or "Rejected")
        yield error_event("invalid_question", decision.message or "Invalid question.", request_id)
        yield done_event("", "error")
        return
    if decision.action == "small_talk":
        yield trace_event(
            "route", "done", "Routing the question", "Greeting / small-talk — no retrieval"
        )
        yield from _handle_small_talk(db, conversation, body.question, decision.message or "")
        return

    history = load_history_messages(db, conversation.id)

    if decision.action == "conversation_meta":
        yield trace_event(
            "route", "done", "Routing the question", "Conversation summary — history only"
        )
        yield from _handle_conversation_meta(db, conversation, body.question, history)
        return
    if decision.action == "explain_simpler":
        yield trace_event(
            "route", "done", "Routing the question", "Explain simpler — rewrite last answer"
        )
        yield from _handle_explain_simpler(
            db, conversation, body.question, history, llm_client, settings, cancel_check
        )
        return

    yield trace_event("route", "done", "Routing the question", "Document question — full RAG path")
    yield from run_document_rag(
        db=db,
        conversation=conversation,
        user=user,
        request_id=request_id,
        question=body.question,
        history=history,
        settings=settings,
        llm_client=llm_client,
        cancel_check=cancel_check,
    )


def _handle_small_talk(
    db: Session, conversation: Conversation, question: str, reply: str
) -> Generator[SseEvent, None, None]:
    persist_message(db, conversation.id, MessageRole.USER, question)
    message = persist_message(db, conversation.id, MessageRole.ASSISTANT, reply)
    yield token_event(reply)
    yield done_event(str(message.id), "ok")


def _handle_conversation_meta(
    db: Session,
    conversation: Conversation,
    question: str,
    history: list,
) -> Generator[SseEvent, None, None]:
    """Answer "what did we talk about?" from chat history — no retrieval/LLM."""
    persist_message(db, conversation.id, MessageRole.USER, question)
    if not history:
        reply = (
            "We haven't discussed anything in this chat yet. Ask a question about "
            "the company documents and I'll help."
        )
    else:
        lines = ["Here's what we've covered in this chat so far:"]
        turn = 0
        for message in history:
            if message.role == "user":
                turn += 1
                lines.append(f"{turn}. You asked: {message.content[:240]}")
            elif message.role == "assistant" and turn > 0:
                preview = message.content.replace("\n", " ")[:180]
                lines.append(f"   → {preview}{'…' if len(message.content) > 180 else ''}")
        reply = "\n".join(lines)
    saved = persist_message(db, conversation.id, MessageRole.ASSISTANT, reply)
    yield token_event(reply)
    yield done_event(str(saved.id), "ok")


def _handle_explain_simpler(
    db: Session,
    conversation: Conversation,
    question: str,
    history: list,
    llm_client: LlmClient,
    settings: Settings,
    cancel_check: Callable[[], bool] | None,
) -> Generator[SseEvent, None, None]:
    """Rewrite the last assistant answer in plain words without new retrieval."""
    from app.llm.base import ChatMessage, StreamToken

    persist_message(db, conversation.id, MessageRole.USER, question)
    last_answer = next((m.content for m in reversed(history) if m.role == "assistant"), None)
    if not last_answer:
        reply = (
            "There isn't a previous answer in this chat to simplify yet. "
            "Ask a document question first."
        )
        saved = persist_message(db, conversation.id, MessageRole.ASSISTANT, reply)
        yield token_event(reply)
        yield done_event(str(saved.id), "ok")
        return

    messages = [
        ChatMessage(
            role="system",
            content=(
                "Rewrite the previous assistant answer in simpler, clearer language for a "
                "new employee. Keep every fact, number, date, command and URL exactly the same. "
                "Do not add new facts. Do not call tools. Keep citations like [1] if present."
            ),
        ),
        ChatMessage(role="assistant", content=last_answer),
        ChatMessage(role="user", content="Please explain that in easier wording."),
    ]
    collected: list[str] = []
    try:
        for event in llm_client.stream_chat(
            messages=messages,
            tools=[],
            model=settings.llm_model,
        ):
            if cancel_check is not None and cancel_check():
                break
            if isinstance(event, StreamToken) and event.text:
                collected.append(event.text)
                yield token_event(event.text)
    except Exception:
        reply = (
            "I couldn't simplify that right now. Here is the previous answer again:\n\n"
            + last_answer
        )
        saved = persist_message(db, conversation.id, MessageRole.ASSISTANT, reply)
        yield token_event(reply)
        yield done_event(str(saved.id), "ok")
        return

    answer = "".join(collected).strip() or last_answer
    saved = persist_message(db, conversation.id, MessageRole.ASSISTANT, answer)
    yield done_event(str(saved.id), "ok")
