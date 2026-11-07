"""Top-level chat orchestration (AGENTS.md §5.4): router -> cache ->
retrieve -> no-answer gate -> budget check -> single-flight -> generate.

Every branch here either avoids an LLM call entirely or hands off to
`single_flight_dispatch.run_with_single_flight` for the one path that
actually talks to a model. SSE events: `meta`, `token`, `citations`,
`ticket_offer`, `done`, `error` (§5.4).
"""

import time
from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from app.config import Settings
from app.embeddings.factory import build_embedder
from app.llm.base import LlmClient
from app.llm.prompts import build_messages, truncate_sources_to_token_budget
from app.models import Conversation, MessageRole, User
from app.retrieval.gate import passes_similarity_gate
from app.retrieval.hybrid import retrieve
from app.schemas import ChatRequest
from app.security import allowed_access_levels
from app.security_hardening import matches_injection_pattern
from app.services.abbreviations import expand_abbreviations
from app.services.audit_service import record_audit_event
from app.services.budget_service import check_budget
from app.services.cache_hit_response import cache_hit_response
from app.services.cache_service import cache_scope, get_cached_answer
from app.services.conversation_service import (
    load_history_messages,
    load_or_create_conversation,
    persist_message,
)
from app.services.fallback_responses import budget_degraded_response, no_answer_response
from app.services.query_router import route_question
from app.services.single_flight_dispatch import run_with_single_flight
from app.services.source_prep import build_sources, drop_near_duplicates
from app.services.stream_events import SseEvent, done_event, error_event, meta_event, token_event


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

    # Cheap, log-only prompt-injection flagger (§5.8): never blocks or
    # changes the answer, just gives the admin audit page a signal to
    # review. The real defences are the prompt rules, ACL in SQL, the
    # tool that cannot write, and citation validation (§3.2, §5.11).
    if matches_injection_pattern(body.question):
        record_audit_event(
            db,
            event_type="injection_pattern_flagged",
            request_id=request_id,
            user_id=user.id,
            details={"source": "question", "question": body.question[:500]},
        )

    decision = route_question(body.question, settings.max_question_chars)
    if decision.action == "reject":
        yield error_event("invalid_question", decision.message or "Invalid question.", request_id)
        yield done_event("", "error")
        return
    if decision.action == "small_talk":
        yield from _handle_small_talk(db, conversation, body.question, decision.message or "")
        return

    history = load_history_messages(db, conversation.id)

    if decision.action == "conversation_meta":
        yield from _handle_conversation_meta(db, conversation, body.question, history)
        return
    if decision.action == "explain_simpler":
        yield from _handle_explain_simpler(
            db, conversation, body.question, history, llm_client, settings, cancel_check
        )
        return

    allowed_levels = allowed_access_levels(user)
    scope = cache_scope(allowed_levels)
    # History must be loaded *before* this turn's question is persisted
    # (§5.5 "history excludes old sources" and §5.10 cache safety): doing it
    # the other way round would make every question look like a follow-up
    # to itself, since it would already be the newest row in its own history.
    is_follow_up = len(history) > 0
    # The question is kept even if everything after this fails (§5.9 #1):
    # a Retry button on the frontend can resend it without retyping.
    persist_message(db, conversation.id, MessageRole.USER, body.question)
    # §5.10 cache safety: an answer that depended on conversation history is
    # never cached and never served from the cache.
    cacheable = settings.cache_enabled and not is_follow_up
    # Expand EMP/ACK/etc. for retrieval only — the stored question stays as typed.
    retrieval_question = expand_abbreviations(body.question)

    if cacheable:
        cached = get_cached_answer(
            db,
            question=body.question,
            scope=scope,
            prompt_version=settings.prompt_version,
            model=settings.llm_model,
            allowed_levels=allowed_levels,
        )
        if cached is not None:
            yield from cache_hit_response(
                db, conversation, user, request_id, body.question, cached, settings
            )
            return

    embedder = build_embedder()
    retrieval_start = time.monotonic()
    result = retrieve(
        db=db,
        embedder=embedder,
        question=retrieval_question,
        allowed_levels=allowed_levels,
        top_k=settings.retrieval_top_k,
        candidates=settings.retrieval_candidates,
        hybrid_enabled=settings.hybrid_enabled,
    )
    retrieval_ms = int((time.monotonic() - retrieval_start) * 1000)

    if not passes_similarity_gate(result.best_vector_similarity, settings.min_similarity):
        yield from no_answer_response(
            db, conversation, user, request_id, body.question, result, retrieval_ms, settings
        )
        return

    budget = check_budget(
        db,
        user.id,
        daily_token_cap_per_user=settings.daily_token_cap_per_user,
        daily_cost_cap_usd=settings.daily_cost_cap_usd,
    )
    if budget.degraded:
        yield from budget_degraded_response(
            db,
            conversation,
            user,
            request_id,
            body.question,
            result,
            retrieval_ms,
            settings,
            budget.reason or "unknown",
        )
        return

    sources = truncate_sources_to_token_budget(
        drop_near_duplicates(build_sources(result.chunks)), settings.max_context_tokens
    )
    messages = build_messages(history=history, sources=sources, question=body.question)

    yield from run_with_single_flight(
        db=db,
        conversation=conversation,
        user=user,
        request_id=request_id,
        question=body.question,
        sources=sources,
        retrieval_result=result,
        messages=messages,
        llm_client=llm_client,
        settings=settings,
        scope=scope,
        cacheable=cacheable,
        embedder=embedder,
        retrieval_ms=retrieval_ms,
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
    from app.llm.base import ChatMessage

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

    from app.llm.base import StreamToken

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
