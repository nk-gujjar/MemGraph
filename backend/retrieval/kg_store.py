import networkx as nx
from backend.db.sqlite import SessionLocal, KGTriple

class KGStore:
    def __init__(self):
        pass
        
    def add_triple(self, session_id: str, s: str, p: str, o: str):
        db = SessionLocal()
        try:
            triple = KGTriple(
                session_id=session_id,
                subject=s,
                predicate=p,
                object_=o
            )
            db.add(triple)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to add triple: {e}")
        finally:
            db.close()

    def query_triples(self, session_id: str, entities: list[str]) -> list[dict]:
        db = SessionLocal()
        triples = []
        try:
            # Query elements where subject or object matching the entities
            res = db.query(KGTriple).filter(
                (KGTriple.session_id == session_id) & 
                (KGTriple.subject.in_(entities) | KGTriple.object_.in_(entities))
            ).all()
            
            for t in res:
                triples.append({
                    "subject": t.subject,
                    "predicate": t.predicate,
                    "object": t.object_
                })
        except Exception as e:
            print(f"Failed to query triples: {e}")
        finally:
            db.close()
            
        return triples

kg_store = KGStore()
