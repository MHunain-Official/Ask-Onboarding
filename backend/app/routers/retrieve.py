"""Debug/eval retrieval endpoint (AGENTS.md §5.3).

Any authenticated user may call this — it is used by the eval harness and
by admins debugging an answer — but the ACL filter still applies: an
employee calling this endpoint can never see a manager-only chunk, exactly
like the chat endpoint that will be built in Phase 4.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.embeddings.factory import build_embedder
from app.models import User
from app.retrieval.gate import passes_similarity_gate
from app.retrieval.hybrid import retrieve
from app.schemas import RetrievedChunkItem, RetrieveRequest, RetrieveResponse
from app.security import allowed_access_levels, require_user

router = APIRouter(prefix="/api", tags=["retrieval"])


@router.post("/retrieve", response_model=RetrieveResponse)
def retrieve_chunks(
    body: RetrieveRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RetrieveResponse:
    settings = get_settings()
    top_k = body.top_k or settings.retrieval_top_k
    embedder = build_embedder()

    result = retrieve(
        db=db,
        embedder=embedder,
        question=body.question,
        allowed_levels=allowed_access_levels(user),
        top_k=top_k,
        candidates=settings.retrieval_candidates,
        hybrid_enabled=settings.hybrid_enabled,
    )

    items = [
        RetrievedChunkItem(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            filename=chunk.filename,
            page=chunk.page,
            heading=chunk.heading,
            text=chunk.text,
            score=chunk.score,
        )
        for chunk in result.chunks
    ]
    return RetrieveResponse(
        items=items,
        best_similarity=result.best_vector_similarity,
        passes_gate=passes_similarity_gate(result.best_vector_similarity, settings.min_similarity),
    )
