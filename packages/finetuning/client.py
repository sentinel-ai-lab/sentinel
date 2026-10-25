"""
Sentinel — Compliance Model Client

Client for invoking the fine-tuned Qwen-2.5-7B LoRA compliance classifier
(kishanaik5/sentinel-compliance-qwen25-7b-lora) or running fallback review.

Taxonomy:
  - COMPLIANT: Factual, verified statements with appropriate citations.
  - NEEDS_DISCLAIMER: Forward-looking statements requiring mandatory risk disclaimers.
  - UNSUPPORTED: Assertions lacking factual backing in disclosures.
  - ADVICE_VIOLATION: Direct investment advice, buy/sell recommendations, or price targets.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

from packages.common.config import get_settings

load_dotenv("infra/.env")

ComplianceLabel = Literal["COMPLIANT", "NEEDS_DISCLAIMER", "UNSUPPORTED", "ADVICE_VIOLATION"]

VALID_LABELS: set[str] = {
    "COMPLIANT",
    "NEEDS_DISCLAIMER",
    "UNSUPPORTED",
    "ADVICE_VIOLATION",
}

DISCLAIMER_TEXT = (
    "\n\n---\n*Past performance is not indicative of future results. "
    "This content is for informational purposes only and does not constitute "
    "investment advice under SEBI regulations.*"
)

ALPACA_PROMPT_TEMPLATE = (
    "Below is an instruction that describes a task, paired with an input that provides further "
    "context. Write a response that appropriately completes the request.\n\n"
    "### Instruction:\n"
    "Classify this financial claim for compliance.\n\n"
    "### Input:\n"
    "{input}\n\n"
    "### Response:\n"
)


@dataclass
class ComplianceClassification:
    label: str
    explanation: str
    rewrite: str
    raw_output: str
    latency_ms: float
    model_used: str


@dataclass
class ComplianceReviewReport:
    audited_text: str
    compliance_summary: str
    audit_trace: list[ComplianceClassification] = field(default_factory=list)
    has_violations: bool = False
    needs_disclaimer: bool = False
    model_used: str = "unknown"

    @property
    def claims_evaluated(self) -> int:
        return len(self.audit_trace)


def parse_compliance_output(
    raw_text: str,
    original_input: str,
    latency_ms: float = 0.0,
    model_used: str = "qwen-2.5-7b-lora",
) -> ComplianceClassification:
    """
    Parses the Alpaca response output into structured fields.

    Expected formats:
      "<LABEL>: <explanation>. Rewrite: <rewritten sentence>"
      or
      "Label: <LABEL>\nExplanation: <exp>\nRewrite: <rew>"
    """
    clean_text = raw_text.strip()
    if clean_text.startswith("### Response:"):
        clean_text = clean_text.replace("### Response:", "").strip()

    detected_label = "COMPLIANT"
    explanation = clean_text
    rewrite = original_input

    # Check for direct label prefix e.g. "ADVICE_VIOLATION: ..."
    for label in VALID_LABELS:
        pattern = rf"^(?:Label:\s*)?({label})[:\s-]+"
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            detected_label = label
            remainder = clean_text[match.end() :].strip()

            # Separate rewrite if present
            rewrite_match = re.search(r"\bRewrite:\s*(.*)$", remainder, re.IGNORECASE | re.DOTALL)
            if rewrite_match:
                rewrite = rewrite_match.group(1).strip()
                explanation = remainder[: rewrite_match.start()].strip()
            else:
                explanation = remainder
            break

    # If no rewrite was specified in output, default to original input
    if not rewrite or rewrite == original_input:
        if detected_label == "COMPLIANT":
            rewrite = original_input

    return ComplianceClassification(
        label=detected_label,
        explanation=explanation or "No explanation provided.",
        rewrite=rewrite or original_input,
        raw_output=raw_text,
        latency_ms=latency_ms,
        model_used=model_used,
    )


class ComplianceModelClient:
    """
    Unified client for the fine-tuned Qwen compliance model.
    Supports Hugging Face Inference API, dedicated endpoints, and Gemini fallback.
    """

    def __init__(
        self,
        model_id: str | None = None,
        hf_token: str | None = None,
        endpoint_url: str | None = None,
        backend: str | None = None,
    ) -> None:
        settings = get_settings()
        self.model_id = model_id or settings.compliance_model_id
        self.hf_token = hf_token or settings.hf_token or os.getenv("HF_TOKEN", "")
        self.endpoint_url = endpoint_url or settings.compliance_endpoint_url
        self.backend = backend or settings.compliance_backend

    def classify_claim(self, claim: str) -> ComplianceClassification:
        """
        Classifies a single financial claim with the fine-tuned model.
        Falls back to Gemini or rule-based heuristics if the remote model is unavailable.
        """
        t0 = time.perf_counter()

        # 1. Custom Endpoint (e.g. vLLM / RunPod TGI / Dedicated HF Endpoint)
        if self.endpoint_url:
            try:
                res = self._call_custom_endpoint(claim)
                latency_ms = (time.perf_counter() - t0) * 1000
                return parse_compliance_output(
                    res, claim, latency_ms=latency_ms, model_used=f"endpoint:{self.endpoint_url}"
                )
            except Exception:
                pass

        # 2. Hugging Face Serverless / Router Inference API
        if self.hf_token and self.backend in ("auto", "huggingface"):
            try:
                res = self._call_hf_inference_api(claim)
                latency_ms = (time.perf_counter() - t0) * 1000
                return parse_compliance_output(
                    res, claim, latency_ms=latency_ms, model_used=self.model_id
                )
            except Exception:
                pass

        # 3. Fallback: Gemini 2.5 Flash
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                res = self._call_gemini_fallback(claim)
                latency_ms = (time.perf_counter() - t0) * 1000
                return parse_compliance_output(
                    res, claim, latency_ms=latency_ms, model_used="gemini-2.5-flash-fallback"
                )
            except Exception:
                pass

        # 4. Deterministic Rule-Based Fallback (Offline / Test mode)
        latency_ms = (time.perf_counter() - t0) * 1000
        return self._rule_based_fallback(claim, latency_ms)

    def review_draft(
        self,
        draft: str,
        citations: list[dict[str, Any]] | None = None,
    ) -> ComplianceReviewReport:
        """
        Full compliance review of a research brief.
        Splits into statements, runs classification, rewrites advice/unsupported claims,
        and appends disclaimer if forward-looking statements or projections exist.
        """
        if not draft.strip():
            return ComplianceReviewReport(
                audited_text="",
                compliance_summary="Empty draft provided.",
                has_violations=False,
                needs_disclaimer=False,
                model_used="none",
            )

        # Split into distinct sentences / lines
        raw_sentences = [
            s.strip() for s in re.split(r"(?<=[.!?])\s+|\n\n+", draft) if len(s.strip()) > 15
        ]

        if not raw_sentences:
            raw_sentences = [draft.strip()]

        audit_trace: list[ComplianceClassification] = []
        rewritten_sentences: list[str] = []
        has_violations = False
        needs_disclaimer = False
        model_used = self.model_id

        for sentence in raw_sentences:
            classification = self.classify_claim(sentence)
            audit_trace.append(classification)
            model_used = classification.model_used

            if classification.label == "ADVICE_VIOLATION":
                has_violations = True
                rewritten_sentences.append(classification.rewrite)
            elif classification.label == "UNSUPPORTED":
                has_violations = True
                rewritten_sentences.append(classification.rewrite)
            elif classification.label == "NEEDS_DISCLAIMER":
                needs_disclaimer = True
                rewritten_sentences.append(sentence)
            else:
                rewritten_sentences.append(sentence)

        audited_text = " ".join(rewritten_sentences)

        # Check citations coverage
        if not citations and "financial" in draft.lower():
            needs_disclaimer = True

        if needs_disclaimer:
            audited_text = audited_text.rstrip() + DISCLAIMER_TEXT

        # Build summary
        labels_found = [c.label for c in audit_trace]
        summary = (
            f"Evaluated {len(audit_trace)} claims. "
            f"Compliant: {labels_found.count('COMPLIANT')}, "
            f"Needs Disclaimer: {labels_found.count('NEEDS_DISCLAIMER')}, "
            f"Unsupported: {labels_found.count('UNSUPPORTED')}, "
            f"Advice Violations: {labels_found.count('ADVICE_VIOLATION')}."
        )

        return ComplianceReviewReport(
            audited_text=audited_text,
            compliance_summary=summary,
            audit_trace=audit_trace,
            has_violations=has_violations,
            needs_disclaimer=needs_disclaimer,
            model_used=model_used,
        )

    def _call_hf_inference_api(self, claim: str) -> str:
        """Calls Hugging Face router / inference API for the fine-tuned model."""
        prompt = ALPACA_PROMPT_TEMPLATE.format(input=claim)
        url = f"https://router.huggingface.co/hf-inference/models/{self.model_id}"
        headers = {
            "Authorization": f"Bearer {self.hf_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 180,
                "temperature": 0.1,
                "return_full_text": False,
            },
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return str(data[0].get("generated_text", ""))
            if isinstance(data, dict):
                return str(data.get("generated_text", ""))
            return str(data)

    def _call_custom_endpoint(self, claim: str) -> str:
        """Calls an external vLLM / TGI endpoint."""
        prompt = ALPACA_PROMPT_TEMPLATE.format(input=claim)
        headers = {"Content-Type": "application/json"}
        if self.hf_token:
            headers["Authorization"] = f"Bearer {self.hf_token}"

        payload = {
            "inputs": prompt,
            "parameters": {"max_new_tokens": 180, "temperature": 0.1},
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(str(self.endpoint_url), headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return str(data[0].get("generated_text", ""))
            return str(data.get("generated_text", data))

    def _call_gemini_fallback(self, claim: str) -> str:
        """Fallback to Google GenAI for classification."""
        import google.genai as genai
        import google.genai.types as genai_types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        system_instruction = (
            "You are a financial research compliance classifier for Indian equities.\n"
            "Classify the claim into: COMPLIANT, NEEDS_DISCLAIMER, UNSUPPORTED, ADVICE_VIOLATION.\n"
            "Format response strictly as:\n"
            "<LABEL>: <reasoning>. Rewrite: <compliant rewritten sentence>"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=claim,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.1,
            ),
        )
        return response.text or ""

    def _rule_based_fallback(self, claim: str, latency_ms: float) -> ComplianceClassification:
        """Deterministic heuristic fallback when no remote LLM is available."""
        lower = claim.lower()

        # Direct investment advice indicators
        advice_terms = ["buy ", "sell ", "strong buy", "target price", "accumulate", "multibagger"]
        if any(term in lower for term in advice_terms):
            return ComplianceClassification(
                label="ADVICE_VIOLATION",
                explanation="Contains explicit investment recommendation or target price.",
                rewrite=re.sub(r"(?i)\b(buy|sell|strong buy|accumulate)\b", "observe", claim),
                raw_output="ADVICE_VIOLATION: Direct investment recommendation detected.",
                latency_ms=latency_ms,
                model_used="rule-based-fallback",
            )

        # Forward looking prediction indicators
        forward_terms = [
            "will double",
            "expected to surge",
            "guaranteed",
            "projected to hit",
            "likely to",
        ]
        if any(term in lower for term in forward_terms):
            return ComplianceClassification(
                label="NEEDS_DISCLAIMER",
                explanation="Forward-looking projection without mandatory risk caveat.",
                rewrite=claim,
                raw_output="NEEDS_DISCLAIMER: Forward-looking statement detected.",
                latency_ms=latency_ms,
                model_used="rule-based-fallback",
            )

        # Default compliant
        return ComplianceClassification(
            label="COMPLIANT",
            explanation="Factual disclosure or analysis statement.",
            rewrite=claim,
            raw_output="COMPLIANT: Statement is factual and non-advisory.",
            latency_ms=latency_ms,
            model_used="rule-based-fallback",
        )
