# 🛡️ Sentinel — Compliance Model Benchmark Report

## Executive Summary

Phase 4 fine-tuning benchmark results comparing the domain-adapted **Qwen-2.5-7B LoRA** model against the **GPT-4o-mini** baseline and un-finetuned **Base Qwen-2.5-7B** on the held-out test split of 271 Indian equity research claims.

- **Empirical Macro F1:** **0.996** (99.63%) on 271 held-out test claims (Phase 4 target was ≥ 0.84)
- **Accuracy:** **99.63%** (270 / 271 correct classifications)
- **F1 Score Improvement:** **+39.5% relative lift** over GPT-4o-mini baseline (0.996 vs 0.714)
- **Cost Efficiency:** **9x cheaper** ($0.001/query vs $0.009/query)
- **Inference Speed:** **2.7x faster** latency (~612ms vs ~1650ms)
- **Model Adapter:** [`kishanaik5/sentinel-compliance-qwen25-7b-lora`](https://huggingface.co/kishanaik5/sentinel-compliance-qwen25-7b-lora)
- **Kaggle Dataset:** [`kishanknaik/finetuning-banking-fy-25-26-dataset`](https://www.kaggle.com/datasets/kishanknaik/finetuning-banking-fy-25-26-dataset)

---

## 1. Overall Performance Comparison

| Model | Macro F1 | Accuracy | Latency (p50) | Latency (p95) | Cost / 1k Queries |
|---|---|---|---|---|---|
| **Qwen-2.5-7B LoRA (Ours)** | **0.996** | **99.6%** | **~612 ms** | **~785 ms** | **$1.00** |
| GPT-4o-mini (Zero-Shot) | 0.714 | 72.0% | ~1650 ms | ~2100 ms | $9.00 |
| Base Qwen-2.5-7B (Zero-Shot) | 0.582 | 59.0% | ~620 ms | ~850 ms | $1.00 |

---

## 2. Per-Class Breakdown (Held-out Test Split, n=271)

```
                  precision    recall  f1-score   support

       COMPLIANT       1.00      1.00      1.00        81
NEEDS_DISCLAIMER       0.99      1.00      0.99        68
     UNSUPPORTED       1.00      0.99      0.99        68
ADVICE_VIOLATION       1.00      1.00      1.00        54

        accuracy                           1.00       271
       macro avg       1.00      1.00      1.00       271
    weighted avg       1.00      1.00      1.00       271
```

---

## 3. Training Details

- **Dataset Size:** 2,174 training examples + 271 validation examples + 271 held-out test examples.
- **Hardware:** Kaggle GPU (Tesla T4 16GB).
- **Library:** Unsloth + TRL + PEFT (`unsloth/Qwen2.5-7B-Instruct-bnb-4bit`).
- **Optimization:** LoRA rank = 16, alpha = 32, dropout = 0.05, 4-bit quantization, gradient checkpointing.
- **Training Duration:** 3 epochs, 204 steps, total runtime ~58 minutes (3,486 seconds).
- **Final Training Loss:** 0.5711.
