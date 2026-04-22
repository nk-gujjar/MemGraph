"""
llm_judge.py
────────────
LLM-as-Judge: evaluates RAG response quality using the fast LLM.
Runs ASYNCHRONOUSLY after the response is sent to the user — zero latency impact.

Evaluation dimensions (each scored 0-10):
  faithfulness   — is the answer grounded in context? No hallucinations?
  relevance      — does the answer address the actual question asked?
  completeness   — does the answer cover all aspects of the question?
  coherence      — is the answer well-structured and easy to follow?
  overall        — holistic quality score

Output is written to the JSONL log as a follow-up record keyed by query_id,
so you can correlate and compare MemGraph vs Traditional RAG side by side.
"""

from __future__ import annotations

import json
import re
import asyncio
import time
from datetime import datetime, timezone

import cohere
from backend.config import settings


JUDGE_PROMPT = """You are an expert evaluator for RAG (Retrieval-Augmented Generation) systems.
Your task is to evaluate the quality of an AI assistant's response given the user's question and the retrieved context.

Score each criterion from 0 to 10:
- 0-3: Poor
- 4-6: Acceptable  
- 7-9: Good
- 10: Excellent

EVALUATION CRITERIA:
1. faithfulness (0-10): Is the answer factually grounded in the provided context? Does it avoid hallucination?
2. relevance (0-10): Does the answer directly address what was asked?
3. completeness (0-10): Does the answer cover all important aspects of the question?
4. coherence (0-10): Is the answer well-structured, clear, and easy to follow?
5. overall (0-10): Holistic quality considering all factors.

---

QUESTION:
{query}

RETRIEVED CONTEXT (what the AI had access to):
{context}

AI RESPONSE:
{response}

---

Return ONLY valid JSON in this exact format, no other text:
{{
  "faithfulness": <int 0-10>,
  "relevance": <int 0-10>,
  "completeness": <int 0-10>,
  "coherence": <int 0-10>,
  "overall": <int 0-10>,
  "reasoning": "<1-2 sentence explanation of the overall score>"
}}"""


class LLMJudge:
    def __init__(self):
        self._client = llm_client.cohere

    def evaluate(
        self,
        query: str,
        context: str,
        response: str,
    ) -> dict:
        """
        Synchronous evaluation — call via asyncio.to_thread from async code.

        Returns:
            {
              "faithfulness": int,
              "relevance": int,
              "completeness": int,
              "coherence": int,
              "overall": int,
              "reasoning": str,
              "latency_ms": float,
              "evaluated_at": str (ISO8601)
            }
        """
        start = time.time()
        prompt = JUDGE_PROMPT.format(
            query=query,
            context=context[:3000],    # cap context to avoid token explosion
            response=response[:2000],  # cap response
        )

        try:
            res = self._client.chat(
                message=prompt,
                model=settings.CHAT_MODEL_FAST,
            )
            raw = res.text.strip()

            # Extract JSON — handle cases where the model wraps it in markdown
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                scores = json.loads(json_match.group())
            else:
                scores = json.loads(raw)

            # Validate and clamp all numeric fields to 0-10
            for field in ("faithfulness", "relevance", "completeness", "coherence", "overall"):
                scores[field] = max(0, min(10, int(scores.get(field, 5))))

            scores["reasoning"] = str(scores.get("reasoning", ""))
            scores["latency_ms"] = round((time.time() - start) * 1000, 2)
            scores["evaluated_at"] = datetime.now(timezone.utc).isoformat()
            return scores

        except Exception as e:
            return {
                "faithfulness": -1,
                "relevance": -1,
                "completeness": -1,
                "coherence": -1,
                "overall": -1,
                "reasoning": f"Evaluation failed: {e}",
                "latency_ms": round((time.time() - start) * 1000, 2),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }


# Singleton
llm_judge = LLMJudge()


async def evaluate_async(
    query_id: str,
    session_id: str,
    approach: str,
    query: str,
    context: str,
    response: str,
) -> dict:
    """
    Runs the judge in a thread pool and returns the scores dict.
    The caller (websocket handler) is responsible for writing to the log.
    """
    scores = await asyncio.to_thread(llm_judge.evaluate, query, context, response)

    print(
        f"[Judge] {approach} | overall={scores['overall']}/10 "
        f"faith={scores['faithfulness']} rel={scores['relevance']} "
        f"comp={scores['completeness']} coh={scores['coherence']}"
    )

    return scores
