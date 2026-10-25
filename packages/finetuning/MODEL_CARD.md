---
base_model: unsloth/Qwen2.5-7B-Instruct-bnb-4bit
library_name: peft
license: apache-2.0
language:
- en
pipeline_tag: text-generation
tags:
- financial-nlp
- compliance
- sebi-regulations
- indian-equities
- unsloth
- qwen2
- trl
- lora
---

# 🛡️ Sentinel — Financial Compliance Classifier (Qwen-2.5-7B LoRA)

**Sentinel Compliance Classifier** is a domain-adapted QLoRA adapter built on top of `Qwen/Qwen2.5-7B-Instruct-bnb-4bit`. It is fine-tuned to classify equity research claims for regulatory compliance under Indian securities regulations (SEBI Research Analyst Regulations), identify forward-looking statements requiring disclaimers, and rewrite non-compliant advisory statements into neutral, auditable research text.

- **Developer:** [Kishan K](https://github.com/kishanaik5)
- **Base Model:** `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`
- **Method:** 4-bit QLoRA (Rank=16, Alpha=32, Dropout=0.05)
- **Library:** Unsloth, PEFT, TRL, Hugging Face Hub
- **Dataset:** [Kaggle: Banking FY25-26 Compliance Dataset](https://www.kaggle.com/datasets/kishanknaik/finetuning-banking-fy-25-26-dataset)
- **License:** Apache 2.0

---

## 📊 Benchmark Results

Evaluated on a held-out test split of 271 Indian equity research claims (`test.jsonl`):

| Model | Macro F1 | Accuracy | Latency (p50) | Latency (p95) | Cost / 1k Queries |
|---|---|---|---|---|---|
| **Qwen-2.5-7B LoRA (This Model)** | **0.996** | **99.6%** | **~612 ms** | **~785 ms** | **$1.00** |
| GPT-4o-mini (Zero-Shot Baseline) | 0.714 | 72.0% | ~1,650 ms | ~2,100 ms | $9.00 |
| Base Qwen-2.5-7B (Zero-Shot) | 0.582 | 59.0% | ~620 ms | ~850 ms | $1.00 |

### Per-Class Test Set Metrics (n=271):
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

## 🏷️ Compliance Label Taxonomy

| Label | Description | Action Required |
|---|---|---|
| `COMPLIANT` | Factual, cited statement backed by quarterly filings or annual disclosures. | Preserve verbatim |
| `NEEDS_DISCLAIMER` | Forward-looking growth projection, revenue target, or guidance. | Append risk disclaimer |
| `UNSUPPORTED` | Claim lacks verifiable empirical support in disclosed corporate data. | Flag or rewrite with caveat |
| `ADVICE_VIOLATION` | Direct investment advice, buy/sell calls, or target prices (SEBI RA violation). | Rewrite into neutral observation |

---

## 💻 Quickstart Inference

### 1. Using Unsloth / Transformers + PEFT

```python
from unsloth import FastLanguageModel
import torch

model_id = "kishanaik5/sentinel-compliance-qwen25-7b-lora"
max_seq_length = 512

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=model_id,
    max_seq_length=max_seq_length,
    dtype=None,
    load_in_4bit=True,
)
FastLanguageModel.for_inference(model)

prompt = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request.

### Instruction:
Classify this financial claim for compliance.

### Input:
TCS is poised to rally 30% next quarter based on cloud deal momentum. Buy now.

### Response:
"""

inputs = tokenizer([prompt], return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=150, temperature=0.1)
print(tokenizer.decode(outputs[0], skip_special_tokens=True))
# Output:
# ADVICE_VIOLATION: Direct investment recommendation and price prediction.
# Rewrite: TCS reported cloud contract expansion in its latest quarterly filing.
```

### 2. Using Hugging Face Inference API / Python requests

```python
import requests

API_URL = "https://router.huggingface.co/hf-inference/models/kishanaik5/sentinel-compliance-qwen25-7b-lora"
headers = {"Authorization": "Bearer YOUR_HF_TOKEN"}

payload = {
    "inputs": "### Instruction:\nClassify this financial claim for compliance.\n\n### Input:\nHDFC Bank net profit grew 33.5% YoY to ₹16,373 crore in Q3 FY24.\n\n### Response:\n",
    "parameters": {"max_new_tokens": 120, "temperature": 0.1},
}

response = requests.post(API_URL, headers=headers, json=payload)
print(response.json())
```

---

## ⚙️ Training Details

- **Dataset:** 2,720 curated synthetic examples across Indian equities (BSE/NSE filings).
- **Split:** 80% Train (2,174), 10% Validation (271), 10% Test (271) with stratified class distribution.
- **Hardware:** 1x NVIDIA Tesla T4 GPU on Kaggle.
- **Training Time:** ~58 minutes (3 epochs, 204 steps).
- **Training Loss:** 0.5711.
- **Hyperparameters:**
  - Learning Rate: `2e-4`
  - Batch Size: 8 per device, 4 gradient accumulation steps (effective batch size 32)
  - LoRA Rank: `16`
  - LoRA Alpha: `32`
  - Target Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`

---

## ⚠️ Limitations & Regulatory Notice

This model is intended to assist equity analysts as an automated compliance co-pilot. It is **not** a legal guarantee of compliance and does not substitute for the supervision of a certified SEBI Registered Research Analyst or compliance officer.
