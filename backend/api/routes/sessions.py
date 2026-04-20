from fastapi import APIRouter, HTTPException, Depends
from backend.db.sqlite import get_db, Session as DBSession
from sqlalchemy.orm import Session
import uuid

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

@router.post("")
def create_session(db: Session = Depends(get_db)):
    session_id = str(uuid.uuid4())
    db_sess = DBSession(id=session_id)
    db.add(db_sess)
    db.commit()
    db.refresh(db_sess)
    return {"session_id": session_id}

@router.get("")
def list_sessions(db: Session = Depends(get_db)):
    sessions = db.query(DBSession).order_by(DBSession.last_active.desc()).all()
    return [{
        "id": s.id,
        "created_at": s.created_at,
        "last_active": s.last_active,
        "message_count": s.message_count,
        "tokens_used": s.tokens_used,
        "input_tokens": s.input_tokens,
        "output_tokens": s.output_tokens
    } for s in sessions]

@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    db_sess = db.query(DBSession).filter(DBSession.id == session_id).first()
    if not db_sess:
        raise HTTPException(status_code=404, detail="Session not found")
    
    db.delete(db_sess)
    db.commit()
    # In a real app we'd also trigger deletion of vector store items for this session_id.
    
    return {"status": "deleted"}
