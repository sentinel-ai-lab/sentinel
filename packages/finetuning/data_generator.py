"""
Sentinel — Synthetic fine-tuning data generator (compliance classifier).

Generates Alpaca-format examples for fine-tuning Qwen-2.5-7B into a 4-class
financial-compliance classifier (Phase 4). Each example teaches the model to
label a financial claim and produce a compliant rewrite:

    {"instruction": "Classify this financial claim for compliance.",
     "input":  "<a realistic financial claim>",
     "output": "<LABEL>: <explanation>. Rewrite: <compliant version>",
     "label":  "<one of the 4 labels>"}

Labels & target distribution (per Phase 4 guide):
    COMPLIANT         30%   — factual, hedged/cited, grounded in reported figures
    NEEDS_DISCLAIMER  25%   — forward-looking/performance claims that need a disclaimer
    UNSUPPORTED       25%   — stated as fact with no citation/source
    ADVICE_VIOLATION  20%   — direct investment advice / buy-sell / return predictions

Design goals (crash-safe / resumable):
  * The output file is opened in APPEND mode BEFORE the loop and every batch
    is written + flush()'ed + fsync()'ed the moment it is generated. Nothing is
    held in memory until the end — Ctrl+C at any point keeps everything already
    produced.
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
from collections import Counter

import google.genai as genai
import google.genai.types as genai_types
from dotenv import load_dotenv

load_dotenv("infra/.env")

# ── Configuration ─────────────────────────────────────────────────────────
# NOTE: gemini-2.0-flash is retired — it still appears in models.list() but
# returns 404 "no longer available" on generateContent. The 2.5 flash family
# is the working successor. Overridable via FINETUNE_DATA_MODEL in infra/.env.
MODEL = os.getenv("FINETUNE_DATA_MODEL", "gemini-2.5-flash")
TARGET_TOTAL = 3000
BATCH_SIZE = 20
TOTAL_BATCHES = TARGET_TOTAL // BATCH_SIZE  # 150
OUTPUT_PATH = "packages/finetuning/data/raw_synthetic.jsonl"

SLEEP_BETWEEN_BATCHES = 0.5  # paid tier
RATE_LIMIT_SLEEP = 30.0      # back-off on 429 before the single retry

# The fixed instruction for every example (injected by us, not the model).
INSTRUCTION = "Classify this financial claim for compliance."

# The 4 labels and how many of each to request per 20-example batch.
# 6 + 5 + 5 + 4 = 20  →  30% / 25% / 25% / 20% overall.
LABEL_COUNTS: dict[str, int] = {
    "COMPLIANT": 6,
    "NEEDS_DISCLAIMER": 5,
    "UNSUPPORTED": 5,
    "ADVICE_VIOLATION": 4,
}
LABELS = frozenset(LABEL_COUNTS)

# Crisp definitions so the model labels consistently — this drives eval F1.
_LABEL_DEFS = (
    "COMPLIANT: a factual statement grounded in reported/annual-report figures, "
    "properly hedged and (where relevant) cited; no advice, no unsupported claims.\n"
    "NEEDS_DISCLAIMER: a forward-looking or past-performance statement that is "
    "acceptable ONLY if a risk disclaimer is attached "
    "(e.g. 'past performance is not indicative of future results').\n"
    "UNSUPPORTED: a claim asserted as fact with no citation, source, or reported "
    "figure to back it — could be true but is not substantiated.\n"
    "ADVICE_VIOLATION: direct investment advice or a buy/sell/target/return "
    "prediction (e.g. 'will double', 'should buy', 'guaranteed 20% upside')."
)

# Rotated across batches for topical variety over 150 batches.
SECTORS = [
    "IT services", "private-sector banks", "FMCG", "automobiles",
    "pharmaceuticals", "cement", "metals & mining", "oil, gas & energy",
    "capital goods & infrastructure", "paints & consumer durables",
    "telecom", "NBFCs & financials", "real estate", "specialty chemicals",
    "power & utilities",
]

_SYSTEM_PROMPT = (
    "You generate supervised fine-tuning data for an Indian-equities financial "
    "COMPLIANCE CLASSIFIER. Each example teaches the model to classify a single "
    "financial claim into exactly one of four labels, explain why, and rewrite it "
    "into a compliant form.\n\n"
    "Label definitions:\n" + _LABEL_DEFS + "\n\n"
    "Rules:\n"
    "- Claims must sound realistic: use real Indian listed companies (TCS, INFY, "
    "RELIANCE, HDFCBANK, ITC, MARUTI, SUNPHARMA, LT, ASIANPAINT, TITAN, ULTRACEMCO, "
    "TATASTEEL, BHARTIARTL, BAJFINANCE, etc.), rupee figures (₹ crore), and FY years.\n"
    "- The 'output' field MUST start with the exact label, then a colon, a one-line "
    "explanation, then ' Rewrite: ' followed by a compliant version of the claim.\n"
    "- Make examples non-trivial: avoid giving away the label with obvious keywords; "
    "vary phrasing, companies, and difficulty. Do not repeat claims across batches.\n"
    "- Return JSON ONLY — no markdown, no preamble."
)


def _counts_phrase() -> str:
    return ", ".join(f"{n} {label}" for label, n in LABEL_COUNTS.items())


def _build_prompt(sector: str, batch_num: int) -> str:
    """Prompt asking for exactly BATCH_SIZE labelled examples in one sector."""
    return (
        f"Generate exactly {BATCH_SIZE} financial-compliance training examples, "
        f"focused on the '{sector}' sector.\n\n"
        f"Label distribution for this batch (exactly): {_counts_phrase()}.\n\n"
        "Each element of the array is a JSON object with these fields:\n"
        '  "input"  — the financial claim to be classified (one sentence)\n'
        '  "output" — "<LABEL>: <explanation>. Rewrite: <compliant version>"\n'
        '  "label"  — one of COMPLIANT, NEEDS_DISCLAIMER, UNSUPPORTED, '
        "ADVICE_VIOLATION\n\n"
        "The 'label' must match the label that begins 'output'.\n"
        f"(batch seed: {batch_num} — make these distinct from other batches.)\n\n"
        "Return ONLY a JSON array of the 20 objects."
    )


def _strip_fences(raw: str) -> str:
    """Remove ```json / ``` fences if the model added them despite instructions."""
    text = (raw or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text.strip("`")
        if text.lstrip().lower().startswith("json"):
            text = text.lstrip()[4:]
    return text.strip().strip("`").strip()


def _parse_examples(raw: str) -> list[dict]:
    """Extract and validate the JSON array of compliance examples."""
    data = json.loads(_strip_fences(raw))
    if not isinstance(data, list):
        raise ValueError("expected a JSON array")

    examples: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        input_ = item.get("input")
        output = item.get("output")
        label = item.get("label")
        if not (isinstance(input_, str) and isinstance(output, str)
                and isinstance(label, str)):
            continue
        label = label.strip().upper()
        input_, output = input_.strip(), output.strip()
        # Keep only well-formed examples whose label is valid and whose
        # output actually begins with that label (self-consistency check).
        if label not in LABELS or not input_ or not output:
            continue
        if not output.upper().startswith(label):
            continue
        examples.append(
            {
                "instruction": INSTRUCTION,
                "input": input_,
                "output": output,
                "label": label,
            }
        )
    return examples


def _generate_batch(client: genai.Client, batch_num: int) -> list[dict]:
    """
    Generate one batch. On a 429 (rate limit) sleep RATE_LIMIT_SLEEP and retry
    once; if it still fails (or any other error occurs) return [] so the caller
    skips the batch rather than crashing.
    """
    sector = SECTORS[batch_num % len(SECTORS)]
    prompt = _build_prompt(sector, batch_num)
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


def _existing_label_counts(path: str) -> Counter:
    """Tally labels already on disk (for resume + final distribution)."""
    counts: Counter = Counter()
    if not os.path.exists(path):
        return counts
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                counts[json.loads(line).get("label", "?")] += 1
            except json.JSONDecodeError:
                counts["?"] += 1
    return counts


def main() -> None:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set (infra/.env or environment)")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # ── Resume: count examples already on disk ────────────────────────────
    label_counts = _existing_label_counts(OUTPUT_PATH)
    existing = sum(label_counts.values())
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
        _print_distribution(label_counts)
        return

    client = genai.Client(api_key=api_key)

    # ── Open in APPEND mode BEFORE the loop; flush every batch ─────────────
    with open(OUTPUT_PATH, "a", encoding="utf-8") as out:
        for batch_num in range(start_batch, TOTAL_BATCHES):
            examples = _generate_batch(client, batch_num)

            for ex in examples:
                out.write(json.dumps(ex, ensure_ascii=False) + "\n")
                label_counts[ex["label"]] += 1
            out.flush()
            os.fsync(out.fileno())  # force to disk — survive Ctrl+C / crash

            total_written += len(examples)
            print(
                f"Batch {batch_num + 1}/{TOTAL_BATCHES} — "
                f"TOTAL examples so far: {total_written}",
                flush=True,
            )

            time.sleep(SLEEP_BETWEEN_BATCHES)

    print(f"Done. {total_written} examples written to {OUTPUT_PATH}", flush=True)
    _print_distribution(label_counts)


def _print_distribution(counts: Counter) -> None:
    total = sum(counts.values()) or 1
    print("Label distribution:", flush=True)
    for label in LABEL_COUNTS:
        n = counts.get(label, 0)
        print(f"  {label:<16} {n:>5}  ({100 * n / total:4.1f}%)", flush=True)
    other = {k: v for k, v in counts.items() if k not in LABEL_COUNTS}
    if other:
        print(f"  (unexpected labels: {dict(other)})", flush=True)


if __name__ == "__main__":
    main()
