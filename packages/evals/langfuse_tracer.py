"""
Sentinel — Langfuse Observability & Metrics Exporter

Sends evaluation scores, latency traces, and LLM judge ratings
to the self-hosted or cloud Langfuse instance.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv("infra/.env")


class LangfuseEvaluationsExporter:
    """Exports RAGAS scores and qualitative evaluation metrics to Langfuse."""

    def __init__(self) -> None:
        self.public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        self.secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        self.host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        self._client: Any = None
        self._init_client()

    def _init_client(self) -> None:
        if self.public_key and self.secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except Exception:
                self._client = None

    def record_eval_scores(
        self,
        trace_id: str,
        rag_scores: dict[str, float],
        judge_scores: dict[str, Any] | None = None,
        latency_ms: float | None = None,
    ) -> bool:
        """
        Pushes evaluation metric scores to a Langfuse trace.
        Returns True if successfully sent to Langfuse, False if running offline.
        """
        if not self._client or not trace_id:
            return False

        try:
            for metric_name, score_value in rag_scores.items():
                self._client.score(
                    trace_id=trace_id,
                    name=f"ragas_{metric_name}",
                    value=float(score_value),
                )

            if judge_scores:
                for j_name, j_val in judge_scores.items():
                    if isinstance(j_val, (int, float)):
                        self._client.score(
                            trace_id=trace_id,
                            name=f"judge_{j_name}",
                            value=float(j_val),
                        )

            if latency_ms is not None:
                self._client.score(
                    trace_id=trace_id,
                    name="pipeline_latency_ms",
                    value=float(latency_ms),
                )

            return True
        except Exception:
            return False
