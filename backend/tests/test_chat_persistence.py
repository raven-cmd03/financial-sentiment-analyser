"""Chat persistence smoke test.

Proves that `ChatMessage` carries a `citations` JSON column (not `metadata`)
end-to-end through the ORM. This is the back-half of the frontend contract
asserted in `test_schemas.py`.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from app.database import Base
from app.models import ChatMessage, ChatSession


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_chat_message_round_trip_preserves_citations(db_session):
    session = ChatSession(title="Q: AAPL")
    db_session.add(session)
    await db_session.flush()

    citations = [{"article_id": "a-1", "title": "Apple beats"}]
    db_session.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content="How is AAPL trending?",
        )
    )
    db_session.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content="Positively.",
            citations=citations,
        )
    )
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(
                ChatMessage.id
            )
        )
    ).scalars().all()

    assert [m.role for m in rows] == ["user", "assistant"]
    assert rows[0].citations in (None, [], {})  # default
    assert rows[1].citations == citations
