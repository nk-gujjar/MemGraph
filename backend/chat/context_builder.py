from backend.retrieval.retriever import RetrievalResult

class ContextBuilder:
    def __init__(self):
        self.MAX_TOKENS = 3500

    def estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def build(self, retrieval_result: RetrievalResult) -> tuple[str, list]:
        """
        Builds the context string and returns the utilized sources.
        """
        doc_chunks = []
        table_chunks = []
        kg_chunks = []
        lt_memory_chunks = []
        event_memory_chunks = []
        recent_chunks = []
        
        sources = []

        for item in retrieval_result.items:
            typ = item["type"]
            content = item["content"]
            meta = item.get("meta", {})
            
            if typ == "rag_doc":
                snip = f"[Source: {meta.get('filename')}, page {meta.get('page_number')}]\n{content}"
                doc_chunks.append(snip)
                sources.append(meta)
            elif typ == "table":
                snip = f"[Source Table: {meta.get('filename')}]\n{content}"
                table_chunks.append(snip)
                sources.append(meta)
            elif typ == "kg_triple":
                kg_chunks.append(content)
            elif typ == "lt_memory":
                lt_memory_chunks.append(content)
            elif typ == "event_memory":
                event_memory_chunks.append(content)
            elif typ == "last_message":
                recent_chunks.append(content)

        # Assemble string with budget check
        context_parts = []
        current_tokens = 0

        # We append backwards in priority to keep recent conversation?
        # Actually prompt says "Truncate sections in priority order if over budget (preserve recent conversation last)"
        
        def append_section(title, lines, reverse=False):
            nonlocal current_tokens
            if not lines:
                return
            section_str = f"[{title}]\n"
            context_parts.append(section_str)
            current_tokens += self.estimate_tokens(section_str)
            
            # If reverse, we try to preserve from the end (like recent conversation)
            items = reversed(lines) if reverse else lines
            added_lines = []
            
            for line in items:
                tokens = self.estimate_tokens(line + "\n")
                if current_tokens + tokens > self.MAX_TOKENS:
                    break
                added_lines.append(line)
                current_tokens += tokens
                
            if reverse:
                added_lines.reverse()
                
            for line in added_lines:
                context_parts.append(line + "\n")

        append_section("RECENT CONVERSATION", recent_chunks, reverse=True)
        append_section("USER PROFILE", event_memory_chunks)
        append_section("CONVERSATION MEMORY", lt_memory_chunks)
        append_section("KNOWLEDGE GRAPH", kg_chunks)
        append_section("TABLE DATA", table_chunks)
        append_section("DOCUMENT CONTEXT", doc_chunks)

        return "\n".join(context_parts), sources

context_builder = ContextBuilder()
