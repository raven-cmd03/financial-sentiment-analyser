import logging
from typing import AsyncGenerator

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import ChatMessage, ChatSession
from app.services.vector_store import VectorStoreService


class RAGChatEvent(dict):
    """Simple typed wrapper for streamed chat events.

    Emitted events are JSON-serializable dicts with the shape::

        {"token": str}                 # for incremental text
        {"citations": list[dict]}       # emitted once before the first token
    """

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "You are an expert financial research assistant powered by the Financial Sentiment Analyzer platform. "
    "Your role is to help users understand market sentiment, news analysis, and financial trends.\n\n"
    "Guidelines:\n"
    "- Provide clear, data-driven analysis grounded in the retrieved context.\n"
    "- Always cite your sources when referencing specific articles or data points "
    '(e.g., "[Source: Reuters, 2025-01-15]").\n'
    "- If the retrieved context does not contain enough information to answer confidently, "
    "say so rather than speculating.\n"
    "- Present balanced viewpoints — mention both bullish and bearish signals when relevant.\n"
    "- Use financial terminology accurately but explain complex concepts when needed.\n\n"
    "IMPORTANT DISCLAIMER: Your analysis is for informational and educational purposes only. "
    "It does not constitute financial advice. Users should consult a qualified financial advisor "
    "before making investment decisions."
)


class RAGChatService:
    def __init__(self, vector_store: VectorStoreService | None = None):
        self._llm = ChatGroq(
            model=settings.GROQ_MODEL,
            api_key=settings.GROQ_API_KEY,
            temperature=0.3,
            streaming=True,
        )
        self._vector_store = vector_store or VectorStoreService()

    async def chat(
        self,
        session_id: int,
        user_message: str,
        db: AsyncSession,
    ) -> AsyncGenerator[dict, None]:
        """Stream a chat turn.

        Yields dicts of shape ``{"token": str}`` or ``{"citations": [...]}``.
        The caller is responsible for JSON-encoding them before sending over SSE.
        """
        session = await db.get(ChatSession, session_id)
        if not session:
            raise ValueError(f"Chat session {session_id} not found")

        # Load recent chat history BEFORE persisting the new user message so it
        # isn't duplicated in the LLM turn (we append the current question
        # explicitly below with retrieved context attached).
        history_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
        )
        history_rows = list(reversed(history_result.scalars().all()))

        # Persist the user message now that history is captured.
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        db.add(user_msg)
        await db.flush()

        # Retrieve relevant docs.
        retrieved = self._vector_store.search(user_message, n_results=5)
        context_parts: list[str] = []
        citations: list[dict] = []
        for hit in retrieved:
            meta = hit.get("metadata", {})
            doc_text = hit.get("document", "")
            source_label = meta.get("source", meta.get("ticker", "unknown"))
            context_parts.append(f"[{source_label}] {doc_text}")
            citations.append(
                {
                    "id": hit.get("id", ""),
                    "title": meta.get("title", source_label),
                    "source": source_label,
                    "url": meta.get("url", ""),
                    "type": meta.get("type", ""),
                }
            )

        context_block = (
            "\n\n".join(context_parts) if context_parts else "No relevant documents found."
        )

        messages: list = [SystemMessage(content=SYSTEM_PROMPT)]
        for msg in history_rows:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        messages.append(
            HumanMessage(
                content=(
                    f"Retrieved context:\n{context_block}\n\n"
                    f"User question: {user_message}"
                )
            )
        )

        # Emit citations once up-front so the client can render them while
        # tokens stream in.
        yield {"citations": citations}

        full_response: list[str] = []
        async for chunk in self._llm.astream(messages):
            token = chunk.content
            if token:
                full_response.append(token)
                yield {"token": token}

        # Persist assistant response.
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content="".join(full_response),
            citations=citations,
        )
        db.add(assistant_msg)
        await db.flush()
