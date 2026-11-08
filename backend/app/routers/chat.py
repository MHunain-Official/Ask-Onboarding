"""`POST /api/chat/stream` (SSE) and conversation history (AGENTS.md §5.4,
§6). Access control: a user may only load/continue their own conversation
(`load_or_create_conversation` silently starts a new one otherwise).
"""

import uuid

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.config import Settings, get_settings
from app.database import get_db
from app.llm.base import LlmClient
from app.llm.factory import get_llm_client
from app.models import Conversation, LlmCall, Message, MessageRole, Ticket, User
from app.schemas import (
    ChatRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationPublic,
    MessagePublic,
)
from app.security import require_csrf_header, require_user
from app.security_hardening import require_chat_rate_limit
from app.services.answer_service import stream_chat_answer
from app.services.audit_service import record_audit_event
from app.services.conversation_service import title_from_question

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat/stream",
    dependencies=[Depends(require_csrf_header), Depends(require_chat_rate_limit)],
)
def chat_stream(
    body: ChatRequest,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    llm_client: LlmClient = Depends(get_llm_client),
) -> EventSourceResponse:
    request_id = getattr(request.state, "request_id", "")

    def cancel_check() -> bool:
        """Best-effort disconnect detection (§5.9 #10): `sse-starlette`
        runs this sync generator in a worker thread; bridging back to the
        request's own event loop is how it can still ask "did the client
        go away?" between tokens without blocking that loop itself."""
        try:
            return bool(anyio.from_thread.run(request.is_disconnected))
        except Exception:  # noqa: BLE001 - never let disconnect detection crash the stream
            return False

    events = stream_chat_answer(
        db=db,
        user=user,
        request_id=request_id,
        body=body,
        settings=settings,
        llm_client=llm_client,
        cancel_check=cancel_check,
    )
    return EventSourceResponse(events)


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    user: User = Depends(require_user), db: Session = Depends(get_db)
) -> ConversationListResponse:
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .all()
    )
    # Older rows may still have a null title — fill from the first user message.
    items = [_conversation_public(db, conversation) for conversation in conversations]
    return ConversationListResponse(items=items)


def _conversation_public(db: Session, conversation: Conversation) -> ConversationPublic:
    title = conversation.title
    if not title:
        first = (
            db.query(Message)
            .filter(
                Message.conversation_id == conversation.id,
                Message.role == MessageRole.USER,
            )
            .order_by(Message.created_at.asc())
            .first()
        )
        if first is not None:
            title = title_from_question(first.content)
            conversation.title = title
            db.commit()
    return ConversationPublic(
        id=conversation.id,
        title=title or "New chat",
        created_at=conversation.created_at,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> ConversationDetailResponse:
    conversation = _owned_conversation(db, conversation_id, user)
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=[MessagePublic.model_validate(m) for m in messages],
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def delete_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    """Users may delete only their own chats. Messages cascade; tickets and
    llm_calls keep their rows but drop the conversation link so audit history
    is not erased by a sidebar cleanup."""
    conversation = _owned_conversation(db, conversation_id, user)
    title = conversation.title
    db.query(Ticket).filter(Ticket.conversation_id == conversation.id).update(
        {Ticket.conversation_id: None},
        synchronize_session=False,
    )
    db.query(LlmCall).filter(LlmCall.conversation_id == conversation.id).update(
        {LlmCall.conversation_id: None},
        synchronize_session=False,
    )
    db.delete(conversation)
    db.commit()
    record_audit_event(
        db,
        event_type="conversation_deleted",
        request_id=getattr(request.state, "request_id", None),
        user_id=user.id,
        details={"conversation_id": str(conversation_id), "title": title},
    )


def _owned_conversation(db: Session, conversation_id: uuid.UUID, user: User) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conversation
