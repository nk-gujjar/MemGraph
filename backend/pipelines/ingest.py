import asyncio
import time
from unstructured.partition.auto import partition
from unstructured.documents.elements import Table as UnstructuredTable
from backend.pipelines.text_pipeline import text_pipeline
from backend.pipelines.table_pipeline import table_pipeline
from backend.pipelines.classifier import strategy_classifier
from backend.db.sqlite import SessionLocal, UploadedFile
from backend.observability.langfuse_client import lf_client

async def process_document(session_id: str, file_path: str, filename: str):
    start_time = time.time()
    
    print(f"\n--- Ingestion started for {filename} (Session: {session_id}) ---")
    
    # 1. Classification
    db = SessionLocal()
    description = None
    try:
        db_file = db.query(UploadedFile).filter(
            UploadedFile.session_id == session_id,
            UploadedFile.filename == filename
        ).first()
        if db_file:
            description = db_file.description
    finally:
        db.close()

    # Optimization: if no description, default to recursive and skip data fetch
    if not description or not description.strip():
        print("No description provided. Defaulting to 'recursive' strategy.")
        strategy = "recursive"
    else:
        print(f"Description provided: '{description}'. Extracting preview for classification...")
        # Quick partition without chunking just to get first few elements
        preview_elements = await asyncio.to_thread(
            partition, filename=file_path, strategy="fast"
        )
        preview_text = "\n".join([str(el) for el in preview_elements[:10]])
        
        strategy = strategy_classifier.classify(preview_text, description)
        print(f"Selected strategy: {strategy}")

    # 2. Parse document using unstructured with chunking
    print(f"Parsing document with {strategy} context...")
    
    # If subsection, we use unstructured chunking
    # If recursive or page, we'll do partitioning first then custom chunking in text_pipeline
    
    if strategy == "subsection":
        elements = await asyncio.to_thread(
            partition,
            filename=file_path,
            chunking_strategy="by_title",
            max_characters=1000,
            new_after_n_chars=800,
            combine_text_under_n_chars=500
        )
    else:
        # Standard partition, let text_pipeline handle chunking
        elements = await asyncio.to_thread(partition, filename=file_path)
        
    print(f"Parsed {len(elements)} elements.")
    
    # 2. Separate text vs tables
    table_elements = []
    text_elements = []
    
    for el in elements:
        # Check if it's a table or contains a table
        if isinstance(el, UnstructuredTable):
            table_elements.append(el)
        elif hasattr(el, 'metadata') and getattr(el.metadata, 'text_as_html', None):
             # Some chunkers might pull tables into elements
             table_elements.append(el)
        else:
            text_elements.append(el)
            
    # Run pipelines concurrently
    tasks = []
    
    # We use to_thread since our pipelines are synchronous
    print(f"Processing {len(text_elements)} text elements and {len(table_elements)} table elements...")
    tasks.append(asyncio.to_thread(text_pipeline.process, session_id, filename, text_elements, strategy))
    tasks.append(asyncio.to_thread(table_pipeline.process, session_id, filename, table_elements))
    
    results = await asyncio.gather(*tasks, return_exceptions=False)
    
    text_count = results[0]
    table_count = results[1]
    
    latency_ms = (time.time() - start_time) * 1000
    
    # Log observation
    lf_client.trace_ingestion(session_id, filename, text_count, table_count, latency_ms)
    
    print(f"Ingestion completed: {text_count} chunks, {table_count} tables.")
    print(f"Latency: {latency_ms:.2f}ms")
    print("-------------------------------------------\n")
    
    return {
        "text_chunks": text_count,
        "tables_processed": table_count
    }
