"""
Sentinel — Compliance Node

Passes the research draft through a Gemini 2.5 Flash call that:
  - Removes investment-advice language
  - Adds risk disclaimers where needed
  - Strips any claims not backed by citations
  - Preserves all factual, cited content unchanged

Falls back to the research_draft (with a disclaimer appended) if the
Gemini API call fails or returns an empty response.

Uses google.genai (new SDK) — google.generativeai is deprecated.
"""

from __future__ import annotations

import os

import google.genai as genai
import google.genai.types as genai_types
from dotenv import load_dotenv

from packages.agents.state import AgentState

load_dotenv("infra/.env")

_SYSTEM_PROMPT = (
    "You are a financial compliance reviewer for an Indian equities research platform.\n\n"
    "Review the draft below and:\n"
    "1. Fix any sentences that constitute investment advice\n"
    "2. Add 'Past performance is not indicative of future results' disclaimer "
    "if forward-looking statements exist\n"
    "3. Remove any unsupported claims not backed by the provided citations\n"
    "4. Keep all factual, cited content unchanged\n\n"
    "Return ONLY the compliant version. No meta-commentary."
)

_DISCLAIMER = (
    "\n\n---\n*Past performance is not indicative of future results. "
    "This content is for informational purposes only and does not constitute "
    "investment advice.*"
)


def compliance_node(state: AgentState) -> AgentState:
    """
    LangGraph node: compliance review via Gemini 2.5 Flash.

    Reads state["research_draft"] and state["citations"].
    Returns state with compliance_result and final_brief populated.
    Falls back to research_draft + disclaimer on API failure.
    """
    draft = state.get("research_draft") or ""

    # If the research node produced nothing, propagate an error
    if not draft.strip():
        return {
            **state,
            "compliance_result": "",
            "final_brief": "",
            "error": "research_draft was empty — cannot run compliance check",
        }

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        prompt = (
            f"Draft:\n{draft}"
            f"\n\nCitations available:\n{state.get('citations', [])}"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
            ),
        )

        # response.text can be None if the model returns only thought parts
        final = response.text

        if not final:
            # Fallback: use research draft + standard disclaimer
            final = draft + _DISCLAIMER

    except Exception:  # noqa: BLE001
        # Any API error (503, rate limit, etc.) → use draft + disclaimer
        final = draft + _DISCLAIMER

    return {
        **state,
        "compliance_result": final,
        "final_brief": final,
    }
