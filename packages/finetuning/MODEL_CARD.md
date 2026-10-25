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
- **License:** Apache 2.0

---

## 📊 Benchmark Results

Evaluated on a held-out test split of 271 Indian equity research claims (`test.jsonl`):

| Model | Macro F1 | Accuracy | Latency (p50) | Latency (p95) | Cost / 1k Queries |
|---|---|---|---|---|---|
| **Qwen-2.5-7B LoRA (This Model)** | **0.852** | **0.856** | **~600 ms** | **~780 ms** | **$1.00** |
| GPT-4o-mini (Zero-Shot Baseline) | 0.714 | 0.720 | ~1,650 ms | ~2,100 ms | $9.00 |
| Base Qwen-2.5-7B (Zero-Shot) | 0.582 | 0.590 | ~620 ms | ~850 ms | $1.00 |

### Key Improvements:
- **+18% Macro F1 improvement** over GPT-4o-mini baseline on compliance classification.
- **3x faster p50 latency** compared to cloud API calls.
- **9x cost reduction** when deployed on dedicated/spot GPU hardware.

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
    "parameters": {"max_new_tokens": 120, "temperature": 0.1}
}

response = requests.post(API_URL, headers=headers, json=payload)
print(response.json())
```

---

## ⚙️ Training Details

- **Dataset Size:** 2,720 curated synthetic examples across Indian equities (BSE/NSE filings).
- **Split:** 80% Train (2,174), 10% Validation (271), 10% Test (271) with stratified class distribution.
- **Hardware:** 1x NVIDIA RTX 4090 24GB VRAM on RunPod spot instance.
- **Training Time:** ~35 minutes (3 epochs).
- **Hyperparameters:**
  - Learning Rate: `2e-4` (Cosine schedule with warmup)
  - Optimizer: `AdamW 8-bit`
  - LoRA Rank: `16`
  - LoRA Alpha: `32`
  - Target Modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`

---

## ⚠️ Limitations & Regulatory Notice

This model is intended to assist equity analysts as an automated compliance co-pilot. It is **not** a legal guarantee of compliance and does not substitute for the supervision of a certified SEBI Registered Research Analyst or compliance officer.
