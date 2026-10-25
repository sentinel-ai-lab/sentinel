"""
Sentinel — Hugging Face Sync Script

Uploads:
  1. Updated MODEL_CARD.md to kishanaik5/sentinel-compliance-qwen25-7b-lora
  2. Dataset splits (train.jsonl, val.jsonl, test.jsonl) to kishanaik5/sentinel-compliance-dataset

Usage:
  python packages/finetuning/upload_to_hf.py --card-only
  python packages/finetuning/upload_to_hf.py --dataset-only
  python packages/finetuning/upload_to_hf.py --all
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

load_dotenv("infra/.env")


def upload_model_card(api: HfApi, token: str, repo_id: str) -> None:
    card_path = Path("packages/finetuning/MODEL_CARD.md")
    if not card_path.exists():
        raise FileNotFoundError(f"{card_path} not found.")

    print(f"Uploading model card to {repo_id}...")
    api.upload_file(
        path_or_fileobj=str(card_path),
        path_in_repo="README.md",
        repo_id=repo_id,
        repo_type="model",
        token=token,
        commit_message="docs: update model card with benchmark results, SEBI taxonomy, and usage",
    )
    print(f"✅ Successfully updated model card at https://huggingface.co/{repo_id}")


def upload_datasets(api: HfApi, token: str, dataset_repo_id: str) -> None:
    data_dir = Path("packages/finetuning/data")
    if not data_dir.exists():
        raise FileNotFoundError(f"{data_dir} not found.")

    print(f"Creating/updating dataset repo: {dataset_repo_id}...")
    api.create_repo(
        repo_id=dataset_repo_id,
        repo_type="dataset",
        token=token,
        exist_ok=True,
    )

    files_to_upload = ["train.jsonl", "val.jsonl", "test.jsonl", "raw_synthetic.jsonl"]
    for filename in files_to_upload:
        file_path = data_dir / filename
        if file_path.exists():
            print(f"Uploading {filename} to {dataset_repo_id}...")
            api.upload_file(
                path_or_fileobj=str(file_path),
                path_in_repo=filename,
                repo_id=dataset_repo_id,
                repo_type="dataset",
                token=token,
                commit_message=f"data: upload {filename} split",
            )
    print(f"✅ Successfully uploaded dataset to https://huggingface.co/datasets/{dataset_repo_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload Sentinel artifacts to Hugging Face")
    parser.add_argument("--model-repo", default="kishanaik5/sentinel-compliance-qwen25-7b-lora")
    parser.add_argument("--dataset-repo", default="kishanaik5/sentinel-compliance-dataset")
    parser.add_argument("--card-only", action="store_true")
    parser.add_argument("--dataset-only", action="store_true")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    token = os.getenv("HF_TOKEN")
    if not token:
        print("❌ Error: HF_TOKEN not found in infra/.env or environment.")
        print("Please configure HF_TOKEN=hf_... in infra/.env to push to Hugging Face.")
        return

    api = HfApi()

    if args.card_only or args.all or (not args.card_only and not args.dataset_only):
        upload_model_card(api, token, args.model_repo)

    if args.dataset_only or args.all:
        upload_datasets(api, token, args.dataset_repo)


if __name__ == "__main__":
    main()
