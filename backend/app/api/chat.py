import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sse_starlette.sse import EventSourceResponse

from app.api.deps import require_api_key
from app.database import get_db
from app.models import ChatSession, ChatMessage
from app.schemas.schemas import (
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionListOut,
    ChatMessageCreate,
)
from app.services.rag_chat import RAGChatService

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(
    body: ChatSessionCreate = None,
    db: AsyncSession = Depends(get_db),
):
    title = body.title if body else "New Chat"
    session = ChatSession(title=title)
    db.add(session)
    await db.flush()
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session.id)
        .options(selectinload(ChatSession.messages))
    )
    return result.scalar_one()


@router.get("/sessions", response_model=list[ChatSessionListOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            ChatSession.id,
            ChatSession.title,
            ChatSession.created_at,
            ChatSession.updated_at,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    )
    rows = result.all()
    return [
        ChatSessionListOut(
            id=r.id,
            title=r.title,
            created_at=r.created_at,
            updated_at=r.updated_at,
            message_count=r.message_count,
        )
        for r in rows
    ]


@router.get("/sessions/{session_id}", response_model=ChatSessionOut)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: int,
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    rag = RAGChatService()

    async def event_generator():
        try:
            async for event in rag.chat(session_id, body.content, db):
                # Each event is a dict like {"token": "..."} or {"citations": [...]};
                # clients parse `evt.data` as JSON.
                yield {"data": json.dumps(event)}
            await db.commit()
            yield {"data": "[DONE]"}
        except Exception:
            logger.exception("Error streaming chat response for session %d", session_id)
            try:
                await db.rollback()
            except Exception:
                pass
            yield {
                "event": "error",
                "data": json.dumps(
                    {"error": "An error occurred while generating the response."}
                ),
            }

    return EventSourceResponse(event_generator())


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    await db.delete(session)
    await db.flush()
