from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


def render_messages(tokenizer: Any, row: dict[str, Any]) -> str:
    messages = row.get("messages")
    if not isinstance(messages, list):
        raise ValueError("SFT row must contain messages list")
    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
    rendered = []
    for message in messages:
        rendered.append(f"<|{message['role']}|>\n{message['content']}")
    return "\n".join(rendered) + "\n"


def tokenize_rows(tokenizer: Any, rows: list[dict[str, Any]], max_length: int) -> list[dict[str, Any]]:
    texts = [render_messages(tokenizer, row) for row in rows]
    encoded = tokenizer(
        texts,
        truncation=True,
        max_length=max_length,
        padding=False,
    )
    return [
        {"input_ids": input_ids, "attention_mask": attention_mask, "labels": list(input_ids)}
        for input_ids, attention_mask in zip(encoded["input_ids"], encoded["attention_mask"])
    ]


def train(args: argparse.Namespace) -> dict[str, Any]:
    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Qwen LoRA training requires optional packages: peft and a training-capable transformers/torch setup. "
            "Install them in a GPU training environment before running this script."
        ) from exc

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        torch_dtype=torch.float16 if args.fp16 else None,
        device_map=args.device_map,
    )
    if args.prepare_kbit:
        model = prepare_model_for_kbit_training(model)

    lora_config = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=[item.strip() for item in args.target_modules.split(",") if item.strip()],
    )
    model = get_peft_model(model, lora_config)

    train_rows = tokenize_rows(tokenizer, load_jsonl(args.train), args.max_length)
    validation_rows = tokenize_rows(tokenizer, load_jsonl(args.validation), args.max_length) if args.validation else None

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.eval_batch_size,
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        logging_steps=args.logging_steps,
        save_strategy="epoch",
        eval_strategy="epoch" if validation_rows else "no",
        report_to=[],
        fp16=args.fp16,
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_rows,
        eval_dataset=validation_rows,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )

    train_result = trainer.train()
    eval_metrics = trainer.evaluate() if validation_rows else {}
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    report = {
        "base_model": args.base_model,
        "output_dir": str(output_dir),
        "train": str(args.train),
        "validation": str(args.validation) if args.validation else None,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "train_metrics": train_result.metrics,
        "eval_metrics": eval_metrics,
        "lora": {
            "r": args.lora_r,
            "alpha": args.lora_alpha,
            "dropout": args.lora_dropout,
            "target_modules": [item.strip() for item in args.target_modules.split(",") if item.strip()],
        },
    }
    (output_dir / "training_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a Qwen LoRA adapter on ML_WINK recommendation SFT JSONL.")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("llm/model_candidates/qwen-recommendations-lora"))
    parser.add_argument("--max-length", type=int, default=2048)
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--eval-batch-size", type=int, default=1)
    parser.add_argument("--gradient-accumulation-steps", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--warmup-ratio", type=float, default=0.03)
    parser.add_argument("--logging-steps", type=int, default=10)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--lora-alpha", type=int, default=32)
    parser.add_argument("--lora-dropout", type=float, default=0.05)
    parser.add_argument("--target-modules", default="q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--fp16", action="store_true")
    parser.add_argument("--prepare-kbit", action="store_true")
    return parser.parse_args()


def main() -> None:
    report = train(parse_args())
    print(json.dumps({
        "output_dir": report["output_dir"],
        "train_loss": report["train_metrics"].get("train_loss"),
        "eval_loss": report["eval_metrics"].get("eval_loss"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
