import sys
import os
from pathlib import Path

# Add current dir to path
sys.path.append(os.getcwd())

try:
    from traditional_rag.db import init_trad_db, engine
    print(f"Engine URL: {engine.url}")
    print("Attempting to initialize Traditional RAG DB...")
    init_trad_db()
    print("Database initialized successfully.")
    
    # Check if file exists
    db_path = "traditional_rag.db"
    if os.path.exists(db_path):
        print(f"File created: {db_path} (Size: {os.path.getsize(db_path)} bytes)")
        print(f"Permissions: {oct(os.stat(db_path).st_mode)}")
    else:
        print(f"WARNING: Database initialization claimed success but {db_path} is missing!")
except Exception as e:
    print(f"ERROR during initialization: {e}")
    import traceback
    traceback.print_exc()

try:
    from backend.db.sqlite import init_db
    print("\nAttempting to initialize MemGraph DB...")
    init_db()
    print("MemGraph DB initialized successfully.")
except Exception as e:
    print(f"ERROR during MemGraph initialization: {e}")
