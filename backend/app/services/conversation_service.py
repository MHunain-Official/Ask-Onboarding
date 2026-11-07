"""Conversation load/create and message history/persistence for the chat
endpoint (AGENTS.md §5.4).
"""

import uuid

from sqlalchemy.orm import Session

from app.llm.base import ChatMessage
from app.models import Conversation, Message, MessageRole, User

# Keep enough turns so "what did we talk about an hour ago" still works in
# a busy chat without blowing the context window (paired with token budget).
MAX_HISTORY_TURNS = 12


def load_or_create_conversation(
    db: Session, user: User, conversation_id: uuid.UUID | None
) -> Conversation:
    """A `conversation_id` the user does not own is treated as "not found"
    and silently starts a fresh conversation, rather than 403ing and
    revealing that the id belongs to someone else."""
    if conversation_id is not None:
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None and conversation.user_id == user.id:
            return conversation

    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def load_history_messages(
    db: Session, conversation_id: uuid.UUID, max_turns: int = MAX_HISTORY_TURNS
) -> list[ChatMessage]:
    """Last `max_turns` user/assistant pairs, content only (AGENTS.md §5.5:
    history "excludes old sources" — safe here because a persisted
    `Message.content` is always the final cited text, never a raw SOURCES
    block)."""
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(max_turns * 2)
        .all()
    )
    rows.reverse()
    return [ChatMessage(role=row.role.value, content=row.content) for row in rows]


def persist_message(
    db: Session,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    *,
    citations: list[dict[str, object]] | None = None,
    ticket_offer: bool = False,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        citations=citations,
        ticket_offer=ticket_offer,
    )
    db.add(message)
    # First user question becomes the sidebar title (once).
    if role == MessageRole.USER:
        conversation = db.get(Conversation, conversation_id)
        if conversation is not None and not conversation.title:
            conversation.title = title_from_question(content)
    db.commit()
    db.refresh(message)
    return message


def title_from_question(question: str, max_length: int = 72) -> str:
    """Short, single-line label for the conversation history sidebar."""
    cleaned = " ".join(question.strip().split())
    if not cleaned:
        return "New chat"
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"
