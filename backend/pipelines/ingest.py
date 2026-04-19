import asyncio
import time
from unstructured.partition.auto import partition
from unstructured.documents.elements import Table as UnstructuredTable
from backend.pipelines.text_pipeline import text_pipeline
from backend.pipelines.table_pipeline import table_pipeline
from backend.observability.langfuse_client import lf_client

async def process_document(session_id: str, file_path: str, filename: str):
    start_time = time.time()
    
    print(f"\n--- Ingestion started for {filename} (Session: {session_id}) ---")
    
    # 1. Parse document using unstructured with chunking
    print("Parsing document and chunking by title...")
    elements = partition(
        filename=file_path,
        chunking_strategy="by_title",
        max_characters=1000,
        new_after_n_chars=800,
        combine_text_under_n_chars=500
    )
    print(f"Parsed {len(elements)} chunked elements.")
    
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
    tasks.append(asyncio.to_thread(text_pipeline.process, session_id, filename, text_elements))
    tasks.append(asyncio.to_thread(table_pipeline.process, session_id, filename, table_elements))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    text_count = results[0] if not isinstance(results[0], Exception) else 0
    table_count = results[1] if not isinstance(results[1], Exception) else 0
    
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
