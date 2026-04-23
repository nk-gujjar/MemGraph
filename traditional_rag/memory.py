"""
Traditional RAG — Sliding-Window Short-Term Memory

Strategy:
  • Keep the last SHORT_TERM_WINDOW messages verbatim (e.g. 6 = 3 turns)
  • When the total history > SUMMARY_TRIGGER messages, compress the oldest
    messages into a rolling summary using the fast LLM, then delete them.
  • Context passed to LLM = [summary (if any)] + [last N messages]

No long-term vector memory, no KG, no event extraction — intentionally.
"""

import asyncio
import cohere
from datetime import datetime

from traditional_rag.config import trad_settings
from traditional_rag.db import TradSessionLocal, TradChatMessage, TradChatSummary


from backend.llm_config import llm_client

class TradMemory:
    def __init__(self):
        self.cohere_client = llm_client.cohere

    # ── Message persistence ───────────────────────────────────────────────────

    def add_message(self, session_id: str, role: str, content: str):
        db = TradSessionLocal()
        try:
            db.add(TradChatMessage(session_id=session_id, role=role, content=content))
            db.commit()
        finally:
            db.close()

    def get_all_messages(self, session_id: str) -> list[dict]:
        db = TradSessionLocal()
        try:
            msgs = (
                db.query(TradChatMessage)
                .filter(TradChatMessage.session_id == session_id)
                .order_by(TradChatMessage.timestamp.asc())
                .all()
            )
            return [{"role": m.role, "content": m.content, "id": m.id} for m in msgs]
        finally:
            db.close()

    def get_last_messages(self, session_id: str, n: int = None) -> list[dict]:
        n = n or trad_settings.SHORT_TERM_WINDOW
        db = TradSessionLocal()
        try:
            msgs = (
                db.query(TradChatMessage)
                .filter(TradChatMessage.session_id == session_id)
                .order_by(TradChatMessage.timestamp.desc())
                .limit(n)
                .all()
            )
            return [{"role": m.role, "content": m.content} for m in reversed(msgs)]
        finally:
            db.close()

    # ── Rolling summary ───────────────────────────────────────────────────────

    def get_summary(self, session_id: str) -> str:
        db = TradSessionLocal()
        try:
            row = (
                db.query(TradChatSummary)
                .filter(TradChatSummary.session_id == session_id)
                .first()
            )
            return row.summary if row else ""
        finally:
            db.close()

    def _set_summary(self, session_id: str, summary: str):
        db = TradSessionLocal()
        try:
            row = (
                db.query(TradChatSummary)
                .filter(TradChatSummary.session_id == session_id)
                .first()
            )
            if row:
                row.summary = summary
                row.updated_at = datetime.utcnow()
            else:
                db.add(TradChatSummary(session_id=session_id, summary=summary))
            db.commit()
        finally:
            db.close()

    def _delete_old_messages(self, session_id: str, keep_ids: list[int]):
        """Delete all messages NOT in keep_ids for this session."""
        db = TradSessionLocal()
        try:
            (
                db.query(TradChatMessage)
                .filter(
                    TradChatMessage.session_id == session_id,
                    TradChatMessage.id.notin_(keep_ids),
                )
                .delete(synchronize_session=False)
            )
            db.commit()
        finally:
            db.close()

    def maybe_summarize(self, session_id: str):
        """
        If the total message count exceeds SUMMARY_TRIGGER, summarize the old
        messages with the fast LLM and retain only the last SHORT_TERM_WINDOW.
        This is a synchronous call — run via asyncio.to_thread when needed.
        """
        all_msgs = self.get_all_messages(session_id)
        total = len(all_msgs)
        window = trad_settings.SHORT_TERM_WINDOW
        trigger = trad_settings.SUMMARY_TRIGGER

        if total <= trigger:
            return  # nothing to do

        # Messages to compress = everything except the last `window` items
        to_compress = all_msgs[: total - window]
        to_keep = all_msgs[total - window :]
        keep_ids = [m["id"] for m in to_keep]

        if not to_compress:
            return

        # Build summarization prompt
        existing_summary = self.get_summary(session_id)
        history_str = "\n".join(
            [f"{m['role'].upper()}: {m['content']}" for m in to_compress]
        )
        if existing_summary:
            prompt = (
                f"You are summarizing a conversation. Here is the existing summary:\n"
                f"{existing_summary}\n\n"
                f"Now extend/update it with these new messages:\n{history_str}\n\n"
                f"Return a concise updated summary (3-5 sentences max)."
            )
        else:
            prompt = (
                f"Summarize the following conversation history concisely "
                f"(3-5 sentences max):\n\n{history_str}"
            )

        try:
            response = self.cohere_client.chat(
                message=prompt, model=trad_settings.CHAT_MODEL_FAST
            )
            new_summary = response.text.strip()
            self._set_summary(session_id, new_summary)
            self._delete_old_messages(session_id, keep_ids)
            print(f"[TradMemory] Compressed {len(to_compress)} messages into summary.")
        except Exception as e:
            print(f"[TradMemory] Summarization failed: {e}")

    # ── Context builder ───────────────────────────────────────────────────────

    def build_memory_context(self, session_id: str) -> tuple[str, list[dict]]:
        """
        Returns:
          context_str  — formatted string ready to inject into prompt
          last_msgs    — raw list of last messages (for Langfuse / logging)
        """
        summary = self.get_summary(session_id)
        last_msgs = self.get_last_messages(session_id)

        parts = []
        if summary:
            parts.append(f"[CONVERSATION SUMMARY]\n{summary}")
        if last_msgs:
            history_lines = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in last_msgs]
            )
            parts.append(f"[RECENT CONVERSATION]\n{history_lines}")

        return "\n\n".join(parts), last_msgs


trad_memory = TradMemory()
