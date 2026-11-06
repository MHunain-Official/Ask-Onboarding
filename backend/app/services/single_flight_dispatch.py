"""Wraps `generate_and_stream_answer` with single-flight de-duplication
(AGENTS.md §5.10 L5 / §5.12 #21): split out of `answer_service.py` purely
to keep that file under 200 lines.
"""

from collections.abc import Callable, Generator

from sqlalchemy.orm import Session

from app.config import Settings
from app.embeddings.base import Embedder
from app.llm.base import ChatMessage, LlmClient
from app.llm.factory import get_circuit_breaker
from app.llm.prompts import SourceForPrompt
from app.models import Conversation, MessageRole, User
from app.retrieval.hybrid import RetrievalResult
from app.services.answer_generation import generate_and_stream_answer
from app.services.answer_persistence import FinalAnswer
from app.services.cache_service import hash_question
from app.services.conversation_service import persist_message
from app.services.single_flight import Flight, get_single_flight_registry
from app.services.stream_events import SseEvent, citations_event, done_event, ticket_offer_event


def run_with_single_flight(
    *,
    db: Session,
    conversation: Conversation,
    user: User,
    request_id: str,
    question: str,
    sources: list[SourceForPrompt],
    retrieval_result: RetrievalResult,
    messages: list[ChatMessage],
    llm_client: LlmClient,
    settings: Settings,
    scope: str,
    cacheable: bool,
    embedder: Embedder,
    retrieval_ms: int,
    cancel_check: Callable[[], bool] | None,
) -> Generator[SseEvent, None, None]:
    """Only the leader for `key` generates; followers wait and replay the
    leader's final answer. Single-flight only applies to the cacheable
    (first-turn, no history) case — identical follow-up questions in
    different conversations do not share a prompt, so they are not deduped.
    """
    registry = get_single_flight_registry()
    flight: Flight[object] | None = None
    is_leader = True
    key = f"{scope}:{hash_question(question)}:{settings.llm_model}"
    if cacheable:
        flight, is_leader = registry.acquire(key)

    if not is_leader and flight is not None:
        final = registry.wait_for_result(flight)
        if isinstance(final, FinalAnswer):
            yield from _replay_follower(db, conversation, question, final)
            return
        # Leader failed or timed out: fall through and generate independently.

    final_answer: FinalAnswer | None = None
    try:
        final_answer = yield from generate_and_stream_answer(
            db=db,
            conversation=conversation,
            user=user,
            request_id=request_id,
            question=question,
            sources=sources,
            retrieval_result=retrieval_result,
            messages=messages,
            llm_client=llm_client,
            breaker=get_circuit_breaker(),
            settings=settings,
            scope=scope,
            cacheable=cacheable,
            embedder=embedder,
            retrieval_ms=retrieval_ms,
            cancel_check=cancel_check,
        )
    finally:
        if flight is not None:
            registry.release(key, flight, final_answer)


def _replay_follower(
    db: Session, conversation: Conversation, question: str, final: FinalAnswer
) -> Generator[SseEvent, None, None]:
    """A follower never streamed live tokens — it gets the leader's
    finished answer in one block, the same shape as a cache hit."""
    message = persist_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        final.text,
        citations=final.citations or None,
        ticket_offer=final.ticket_offer,
    )
    if final.citations:
        yield citations_event(final.citations)
    if final.ticket_offer and final.suggested_title:
        yield ticket_offer_event(final.suggested_title, question)
    yield done_event(str(message.id), final.status.value)
