"""Document-question path: cache → retrieve → gate → budget → generate.

Split from `answer_service` so that file stays a thin router of chat modes
and this file owns the RAG breadcrumb trail for the retrieval track UI.
"""

import time
from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from app.config import Settings
from app.embeddings.factory import build_embedder
from app.llm.base import LlmClient
from app.llm.prompts import build_messages, truncate_sources_to_token_budget
from app.models import AccessLevel, Conversation, MessageRole, User
from app.retrieval.gate import passes_similarity_gate
from app.retrieval.hybrid import retrieve
from app.security import allowed_access_levels
from app.services.budget_service import check_budget
from app.services.cache_hit_response import cache_hit_response
from app.services.cache_service import cache_scope, get_cached_answer
from app.services.conversation_service import persist_message
from app.services.fallback_responses import budget_degraded_response, no_answer_response
from app.services.follow_up_query import build_retrieval_question
from app.services.single_flight_dispatch import run_with_single_flight
from app.services.source_prep import build_sources, drop_near_duplicates
from app.services.stream_events import SseEvent, trace_event
from app.services.trace_format import format_gate_detail, format_retrieval_detail


def run_document_rag(
    *,
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    history: list,
    settings: Settings,
    llm_client: LlmClient,
    cancel_check: Callable[[], bool] | None,
) -> Generator[SseEvent, None, None]:
    allowed_levels = allowed_access_levels(user)
    scope = cache_scope(allowed_levels)
    # History must be loaded *before* this turn's question is persisted
    # (§5.5 / §5.10): otherwise every question looks like a follow-up to itself.
    is_follow_up = len(history) > 0
    persist_message(db, conversation.id, MessageRole.USER, question)
    cacheable = settings.cache_enabled and not is_follow_up
    # Retrieval may prepend the previous user question for short follow-ups;
    # the LLM still sees `question` + history separately (prompts.py).
    retrieval_question = build_retrieval_question(question, history)

    if retrieval_question != question:
        yield trace_event(
            "expand",
            "done",
            "Expanded retrieval query",
            f"Retrieval query: “{retrieval_question[:200]}”",
        )

    yield trace_event(
        "acl",
        "done",
        "Access filter ready",
        f"Scope “{scope}” — only allowed document levels reach search",
    )

    hit = yield from _cache_branch(
        db,
        conversation,
        user,
        request_id,
        question,
        scope,
        allowed_levels,
        settings,
        cacheable,
        is_follow_up,
    )
    if hit:
        return

    yield from _retrieve_and_answer(
        db=db,
        conversation=conversation,
        user=user,
        request_id=request_id,
        question=question,
        retrieval_question=retrieval_question,
        history=history,
        allowed_levels=allowed_levels,
        scope=scope,
        cacheable=cacheable,
        settings=settings,
        llm_client=llm_client,
        cancel_check=cancel_check,
    )


def _cache_branch(
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    scope: str,
    allowed_levels: list[AccessLevel],
    settings: Settings,
    cacheable: bool,
    is_follow_up: bool,
) -> Generator[SseEvent, None, bool]:
    if not cacheable:
        reason = "follow-up turns are never cached" if is_follow_up else "cache disabled"
        yield trace_event("cache", "skipped", "Checking answer cache", reason)
        return False

    yield trace_event("cache", "running", "Checking answer cache")
    cached = get_cached_answer(
        db,
        question=question,
        scope=scope,
        prompt_version=settings.prompt_version,
        model=settings.llm_model,
        allowed_levels=allowed_levels,
    )
    if cached is not None:
        yield from cache_hit_response(
            db, conversation, user, request_id, question, cached, settings
        )
        return True
    yield trace_event("cache", "done", "Checking answer cache", "Miss — continue to retrieval")
    return False


def _retrieve_and_answer(
    *,
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    retrieval_question: str,
    history: list,
    allowed_levels: list[AccessLevel],
    scope: str,
    cacheable: bool,
    settings: Settings,
    llm_client: LlmClient,
    cancel_check: Callable[[], bool] | None,
) -> Generator[SseEvent, None, None]:
    yield trace_event(
        "retrieve", "running", "Searching documents", "Embedding question · ranking passages"
    )
    embedder = build_embedder()
    started = time.monotonic()
    result = retrieve(
        db=db,
        embedder=embedder,
        question=retrieval_question,
        allowed_levels=allowed_levels,
        top_k=settings.retrieval_top_k,
        candidates=settings.retrieval_candidates,
        hybrid_enabled=settings.hybrid_enabled,
    )
    retrieval_ms = int((time.monotonic() - started) * 1000)
    yield trace_event(
        "retrieve",
        "done",
        "Searching documents",
        format_retrieval_detail(
            result, hybrid_enabled=settings.hybrid_enabled, elapsed_ms=retrieval_ms
        ),
        {
            "chunk_count": len(result.chunks),
            "best_similarity": round(result.best_vector_similarity, 4),
            "hybrid": settings.hybrid_enabled,
            "ms": retrieval_ms,
            "top": [
                {
                    "filename": chunk.filename,
                    "heading": chunk.heading,
                    "score": round(chunk.score, 4),
                }
                for chunk in result.chunks[:5]
            ],
        },
    )

    gate_ok = passes_similarity_gate(result.best_vector_similarity, settings.min_similarity)
    yield trace_event(
        "gate",
        "done" if gate_ok else "failed",
        "Similarity gate",
        format_gate_detail(result.best_vector_similarity, settings.min_similarity, gate_ok),
    )
    if not gate_ok:
        yield from no_answer_response(
            db, conversation, user, request_id, question, result, retrieval_ms, settings
        )
        return

    budget = check_budget(
        db,
        user.id,
        daily_token_cap_per_user=settings.daily_token_cap_per_user,
        daily_cost_cap_usd=settings.daily_cost_cap_usd,
    )
    if budget.degraded:
        yield trace_event(
            "budget",
            "failed",
            "Usage budget",
            f"Over cap ({budget.reason}) — showing passages only",
        )
        yield from budget_degraded_response(
            db,
            conversation,
            user,
            request_id,
            question,
            result,
            retrieval_ms,
            settings,
            budget.reason or "unknown",
        )
        return
    yield trace_event("budget", "done", "Usage budget", "Within daily token and cost caps")

    sources = truncate_sources_to_token_budget(
        drop_near_duplicates(build_sources(result.chunks)), settings.max_context_tokens
    )
    yield trace_event(
        "prompt",
        "done",
        "Built grounded prompt",
        f"{len(sources)} source(s) after dedupe · max {settings.max_context_tokens} context tokens",
    )
    messages = build_messages(history=history, sources=sources, question=question)
    yield from run_with_single_flight(
        db=db,
        conversation=conversation,
        user=user,
        request_id=request_id,
        question=question,
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
