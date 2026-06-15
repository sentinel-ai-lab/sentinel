"""
Sentinel — Synthetic fine-tuning data generator.

Generates instruction/response pairs for fine-tuning a small model on the
Sentinel domain: Indian equity research, annual-report analysis, and
compliant, citation-aware financial answering.

Design goals (crash-safe / resumable):
  * The output file is opened in APPEND mode BEFORE the loop and every batch
    is written + flush()'ed to disk the moment it is generated. Nothing is
    held in memory until the end — Ctrl+C at any point keeps everything that
    was already produced.
  * On restart the existing line count is read and already-completed batches
    are skipped, so a run resumes where it left off.

Uses google.genai (new SDK) — google.generativeai is deprecated.

Run:
    python -u packages/finetuning/data_generator.py
"""

from __future__ import annotations

import json
import os
import time

import google.genai as genai
import google.genai.types as genai_types
from dotenv import load_dotenv

load_dotenv("infra/.env")

# ── Configuration ─────────────────────────────────────────────────────────
# NOTE: gemini-2.0-flash is retired — it still appears in models.list() but
# returns 404 "no longer available" on generateContent. The 2.5 flash family
# is the working successor.
MODEL = "gemini-2.5-flash"
TARGET_TOTAL = 3000
BATCH_SIZE = 20
TOTAL_BATCHES = TARGET_TOTAL // BATCH_SIZE  # 150
OUTPUT_PATH = "packages/finetuning/data/raw_synthetic.jsonl"

SLEEP_BETWEEN_BATCHES = 0.5  # paid tier
RATE_LIMIT_SLEEP = 30.0      # back-off on 429 before the single retry

# Rotated through batches to keep the 3000 examples diverse.
TOPICS = [
    "revenue and profit growth trends from annual reports",
    "margin analysis (gross, EBITDA, net) and what drives them",
    "balance-sheet health: debt, leverage, liquidity ratios",
    "cash-flow quality (operating vs investing vs financing)",
    "return ratios (ROE, ROCE, ROA) and DuPont decomposition",
    "valuation multiples (P/E, P/B, EV/EBITDA) interpretation",
    "segment-wise / geography-wise revenue breakdown",
    "management discussion & analysis (MD&A) key takeaways",
    "risk factors and contingent liabilities disclosure",
    "capital allocation: dividends, buybacks, capex plans",
    "working-capital cycle and inventory / receivables trends",
    "auditor remarks, related-party transactions, governance",
    "sector comparison across Indian listed peers",
    "forward-looking guidance and demand commentary",
    "comparing two fiscal years for the same company",
]

_SYSTEM_PROMPT = (
    "You are creating supervised fine-tuning data for an Indian-equities "
    "research assistant. Produce realistic, high-quality instruction/response "
    "pairs. Responses must be analytical, specific, and cite figures the way a "
    "sell-side analyst would (e.g. 'revenue grew 18% YoY to ₹1,240 cr'). "
    "Add a brief risk disclaimer when the answer is forward-looking. "
    "Never give direct buy/sell advice."
)


def _build_prompt(topic: str, batch_num: int) -> str:
    """Prompt asking Gemini for exactly BATCH_SIZE JSON examples."""
    return (
        f"Generate exactly {BATCH_SIZE} diverse fine-tuning examples about: "
        f"{topic}.\n\n"
        "Each example is a JSON object with two string fields:\n"
        '  "instruction" — a question or task a user would ask an Indian '
        "equity research copilot\n"
        '  "response" — the ideal analyst-grade answer with concrete numbers '
        "and citations like [TICKER, FY2025, p.X]\n\n"
        "Vary companies (use real Indian listed names: TCS, INFY, RELIANCE, "
        "HDFCBANK, ITC, MARUTI, SUNPHARMA, LT, ASIANPAINT, TITAN, etc.), "
        "vary the phrasing, difficulty, and answer length.\n"
        f"(batch seed: {batch_num}, make these distinct from other batches)\n\n"
        "Return ONLY a JSON array of objects. No markdown, no prose."
    )


def _parse_examples(raw: str) -> list[dict]:
    """Extract the JSON array of examples from a model response."""
    text = (raw or "").strip()
    # Strip ```json / ``` fences if the model added them despite instructions.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    text = text.strip().strip("`").strip()

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")

    examples: list[dict] = []
    for item in data:
        if (
            isinstance(item, dict)
            and isinstance(item.get("instruction"), str)
            and isinstance(item.get("response"), str)
            and item["instruction"].strip()
            and item["response"].strip()
        ):
            examples.append(
                {
                    "instruction": item["instruction"].strip(),
                    "response": item["response"].strip(),
                }
            )
    return examples


def _generate_batch(client: genai.Client, batch_num: int) -> list[dict]:
    """
    Generate one batch. On a 429 (rate limit) sleep RATE_LIMIT_SLEEP and retry
    once; if it still fails (or any other error occurs) return [] so the caller
    skips the batch rather than crashing.
    """
    topic = TOPICS[batch_num % len(TOPICS)]
    prompt = _build_prompt(topic, batch_num)
    config = genai_types.GenerateContentConfig(
        system_instruction=_SYSTEM_PROMPT,
        temperature=1.0,
        response_mime_type="application/json",
    )

    for attempt in (1, 2):
        try:
            response = client.models.generate_content(
                model=MODEL, contents=prompt, config=config
            )
            return _parse_examples(response.text)
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            is_rate_limit = "429" in msg or "RESOURCE_EXHAUSTED" in msg
            if is_rate_limit and attempt == 1:
                print(
                    f"  ⚠️  429 rate limit on batch {batch_num + 1} — "
                    f"sleeping {RATE_LIMIT_SLEEP:.0f}s then retrying once...",
                    flush=True,
                )
                time.sleep(RATE_LIMIT_SLEEP)
                continue
            print(
                f"  ⚠️  batch {batch_num + 1} failed "
                f"({'rate limit' if is_rate_limit else 'error'}): "
                f"{msg[:120]} — skipping",
                flush=True,
            )
            return []
    return []


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set (infra/.env or environment)")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # ── Resume: count examples already on disk ────────────────────────────
    existing = 0
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH, encoding="utf-8") as fh:
            existing = sum(1 for line in fh if line.strip())
    start_batch = existing // BATCH_SIZE
    total_written = existing

    if start_batch:
        print(
            f"Resuming: {existing} examples already on disk "
            f"→ skipping first {start_batch} batch(es).",
            flush=True,
        )
    if start_batch >= TOTAL_BATCHES:
        print(
            f"Already at target ({existing} ≥ {TARGET_TOTAL}). Nothing to do.",
            flush=True,
        )
        return

    client = genai.Client(api_key=api_key)

    # ── Open in APPEND mode BEFORE the loop; flush every batch ─────────────
    with open(OUTPUT_PATH, "a", encoding="utf-8") as out:
        for batch_num in range(start_batch, TOTAL_BATCHES):
            examples = _generate_batch(client, batch_num)

            for ex in examples:
                out.write(json.dumps(ex, ensure_ascii=False) + "\n")
            out.flush()
            os.fsync(out.fileno())  # force to disk — survive Ctrl+C / crash

            total_written += len(examples)
            print(
                f"Batch {batch_num + 1}/{TOTAL_BATCHES} — "
                f"TOTAL examples so far: {total_written}",
                flush=True,
            )

            time.sleep(SLEEP_BETWEEN_BATCHES)

    print(
        f"Done. {total_written} examples written to {OUTPUT_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    main()
