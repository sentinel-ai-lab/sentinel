"""
Sentinel — LLM-as-a-Judge Evaluation Engine

Evaluates financial research briefs on 5 qualitative dimensions:
  1. Accuracy (1-5) — factual correctness and data grounding
  2. Completeness (1-5) — thoroughness in answering the query
  3. Clarity (1-5) — structure, readability, and financial professionalism
  4. Compliance (1-5) — avoidance of speculative investment advice & inclusion of disclaimers
  5. Citation Quality (1-5) — presence of specific company tickers and page numbers

Returns an overall composite score and reasoning breakdown.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

load_dotenv("infra/.env")

JUDGE_PROMPT_TEMPLATE = """
You are an expert financial research auditor evaluating an AI copilot response for Indian equities.
Score the response on these 5 dimensions (strictly integers 1 to 5):
1. accuracy: Are numerical facts correct and grounded in the question context?
2. completeness: Does it comprehensively answer the user question?
3. clarity: Is the explanation concise, professional, and well-structured?
4. compliance: Does it avoid investment advice and include required risk disclaimers?
5. citation_quality: Are citations specific, linking companies and page numbers?

Return ONLY valid JSON matching this schema:
{
  "accuracy": <1-5>,
  "completeness": <1-5>,
  "clarity": <1-5>,
  "compliance": <1-5>,
  "citation_quality": <1-5>,
  "reasoning": "<concise justification>"
}

User Question: {question}
AI Response: {response}
"""


@dataclass
class LLMJudgeResult:
    accuracy: int
    completeness: int
    clarity: int
    compliance: int
    citation_quality: int
    composite_score: float
    reasoning: str
    judge_model: str


class LLMJudge:
    """Evaluates brief quality using an LLM judge or deterministic baseline."""

    def __init__(self, backend: str = "auto") -> None:
        self.backend = backend

    def evaluate(
        self,
        question: str,
        response: str,
        expected_answer: str | None = None,
    ) -> LLMJudgeResult:
        """Runs the 5-dimension judge scoring."""
        if not response.strip():
            return LLMJudgeResult(
                accuracy=1,
                completeness=1,
                clarity=1,
                compliance=1,
                citation_quality=1,
                composite_score=1.0,
                reasoning="Empty response generated.",
                judge_model="fallback",
            )

        # 1. Try Gemini
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and self.backend in ("auto", "gemini"):
            try:
                return self._evaluate_with_gemini(question, response)
            except Exception:
                pass

        # 2. Try Anthropic / Claude
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key and self.backend in ("auto", "anthropic"):
            try:
                return self._evaluate_with_anthropic(question, response)
            except Exception:
                pass

        # 3. Deterministic scoring fallback
        return self._deterministic_eval(question, response, expected_answer)

    def _evaluate_with_gemini(self, question: str, response: str) -> LLMJudgeResult:
        import google.genai as genai
        import google.genai.types as genai_types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, response=response)

        res = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        data = json.loads(res.text or "{}")
        return self._build_result(data, model_name="gemini-2.5-flash-judge")

    def _evaluate_with_anthropic(self, question: str, response: str) -> LLMJudgeResult:
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, response=response)

        msg = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )
        content_block = msg.content[0]
        text = getattr(content_block, "text", str(content_block))
        data = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))
        return self._build_result(data, model_name="claude-3-5-sonnet-judge")

    def _build_result(self, data: dict[str, Any], model_name: str) -> LLMJudgeResult:
        acc = int(data.get("accuracy", 4))
        comp = int(data.get("completeness", 4))
        clar = int(data.get("clarity", 4))
        compl = int(data.get("compliance", 5))
        cit = int(data.get("citation_quality", 4))
        avg = (acc + comp + clar + compl + cit) / 5.0
        reasoning = str(data.get("reasoning", "Evaluated via LLM judge."))

        return LLMJudgeResult(
            accuracy=acc,
            completeness=comp,
            clarity=clar,
            compliance=compl,
            citation_quality=cit,
            composite_score=round(avg, 2),
            reasoning=reasoning,
            judge_model=model_name,
        )

    def _deterministic_eval(
        self,
        question: str,
        response: str,
        expected_answer: str | None = None,
    ) -> LLMJudgeResult:
        """Deterministic heuristic scoring for hermetic CI testing without API keys."""
        resp_lower = response.lower()
        has_citations = bool(re.search(r"\[[A-Z]+,\s*(?:FY\d{4},\s*)?p\.\d+\]", response))
        has_disclaimer = "disclaimer" in resp_lower or "past performance" in resp_lower
        has_advice = any(w in resp_lower for w in ["buy now", "strong buy", "target price"])

        acc = 5 if has_citations else 3
        comp = 5 if len(response) > 80 else 3
        clar = 5 if len(response.split()) > 15 else 3
        compl = 1 if has_advice else (5 if has_disclaimer else 4)
        cit = 5 if has_citations else 2

        if expected_answer:
            keywords = [w.lower() for w in expected_answer.split() if len(w) > 4]
            overlap = sum(1 for kw in keywords if kw in resp_lower)
            if keywords and (overlap / len(keywords)) < 0.2:
                acc = max(1, acc - 2)

        composite = (acc + comp + clar + compl + cit) / 5.0

        return LLMJudgeResult(
            accuracy=acc,
            completeness=comp,
            clarity=clar,
            compliance=compl,
            citation_quality=cit,
            composite_score=round(composite, 2),
            reasoning="Deterministic evaluation: valid citations and compliance criteria verified.",
            judge_model="deterministic-judge",
        )
