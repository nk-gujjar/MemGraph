from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import settings
from backend.retrieval.vector_store import vstore
from backend.observability.langfuse_client import lf_client
import time

class TextPipeline:
    def __init__(self):
        # We'll initialize these on demand if needed or different ones for different strategies
        pass

    def process(self, session_id: str, filename: str, elements: list, strategy: str = "recursive") -> int:
        """
        Process unstructured Text elements. Returns number of chunks created.
        """
        # Combine text elements or process them piece by piece
        # elements here are Unstructured elements that are not tables.
        
        chunks = []
        
        if strategy == "recursive":
            # Just join all text and split recursively
            full_text = "\n\n".join([str(el) for el in elements if str(el).strip()])
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=settings.CHUNK_SIZE,
                chunk_overlap=settings.CHUNK_OVERLAP
            )
            split_texts = splitter.split_text(full_text)
            for i, t in enumerate(split_texts):
                chunks.append({
                    "text": t,
                    "metadata": {
                        "filename": filename,
                        "page_number": None, 
                        "chunk_index": i
                    }
                })
        
        elif strategy == "page":
            # Group by page
            pages = {}
            for el in elements:
                page = el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else 0
                if page not in pages:
                    pages[page] = []
                pages[page].append(str(el))
            
            idx = 0
            for page_num, page_texts in sorted(pages.items()):
                page_content = "\n\n".join(page_texts)
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP
                )
                page_chunks = splitter.split_text(page_content)
                for t in page_chunks:
                    chunks.append({
                        "text": t,
                        "metadata": {
                            "filename": filename,
                            "page_number": page_num,
                            "chunk_index": idx
                        }
                    })
                    idx += 1
        
        else: # subsection / default (uses unstructured elements as-is)
            for el in elements:
                page_number = el.metadata.page_number if hasattr(el, 'metadata') and hasattr(el.metadata, 'page_number') else None
                text = str(el)
                if not text.strip():
                    continue
                    
                chunks.append({
                    "text": text,
                    "metadata": {
                        "filename": filename,
                        "page_number": page_number,
                        "chunk_index": len(chunks)
                    }
                })
        
        if not chunks:
            return 0
            
        texts = [c["text"] for c in chunks]
        metas = [c["metadata"] for c in chunks]
        
        start_time = time.time()
        vstore.add_texts(session_id, texts, metas)
        
        return len(texts)

text_pipeline = TextPipeline()
