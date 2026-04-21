"""
Traditional RAG — Session Routes

Exposes routes at BOTH:
  /api/sessions        ← frontend-compatible (used when running standalone on port 8001)
  /trad/api/sessions   ← prefixed (used when sharing server with MemGraph)
"""

import uuid
from fastapi import APIRouter
from traditional_rag.db import TradSessionLocal, TradSession, TradChatMessage


def _create_session():
    session_id = str(uuid.uuid4())
    db = TradSessionLocal()
    try:
        db.add(TradSession(id=session_id))
        db.commit()
    finally:
        db.close()
    return {"session_id": session_id}


def _list_sessions():
    db = TradSessionLocal()
    try:
        sessions = (
            db.query(TradSession)
            .order_by(TradSession.last_active.desc())
            .all()
        )
        return [
            {
                "id": s.id,
                "created_at": s.created_at,
                "last_active": s.last_active,
                "message_count": s.message_count,
                "tokens_used": s.tokens_used,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
            }
            for s in sessions
        ]
    finally:
        db.close()


def _session_messages(session_id: str):
    db = TradSessionLocal()
    try:
        msgs = (
            db.query(TradChatMessage)
            .filter(TradChatMessage.session_id == session_id)
            .order_by(TradChatMessage.timestamp.asc())
            .all()
        )
        return [{"id": m.id, "role": m.role, "content": m.content} for m in msgs]
    finally:
        db.close()


def _delete_session(session_id: str):
    db = TradSessionLocal()
    try:
        sess = db.query(TradSession).filter(TradSession.id == session_id).first()
        if not sess:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Session not found")

        # Clean up related data
        from traditional_rag.db import TradChatMessage, TradChatSummary, TradUploadedFile
        db.query(TradChatMessage).filter(TradChatMessage.session_id == session_id).delete()
        db.query(TradChatSummary).filter(TradChatSummary.session_id == session_id).delete()
        db.query(TradUploadedFile).filter(TradUploadedFile.session_id == session_id).delete()
        db.delete(sess)
        db.commit()
        return {"status": "deleted"}
    finally:
        db.close()


# ── /api/sessions (frontend-compatible, standalone mode on port 8001) ─────────
router = APIRouter(prefix="/api/sessions", tags=["trad-sessions"])

router.post("")(_create_session)
router.get("")(_list_sessions)
router.get("/{session_id}/messages")(_session_messages)
router.delete("/{session_id}")(_delete_session)

# ── /trad/api/sessions (namespaced, shared-server mode) ──────────────────────
trad_router = APIRouter(prefix="/trad/api/sessions", tags=["trad-sessions"])

trad_router.post("")(_create_session)
trad_router.get("")(_list_sessions)
trad_router.get("/{session_id}/messages")(_session_messages)
trad_router.delete("/{session_id}")(_delete_session)
