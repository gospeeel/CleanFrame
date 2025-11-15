#!/usr/bin/env python3
"""
train_rubert.py

Продвинутый тренер для классификации уровней (0..4) на базе RuBERT (или любой другой модели HF).
Поддерживает: stratified split, data collator, fp16, early stopping, layer-freeze, save_best_model, test evaluation.
"""

import os
import argparse
import logging
import json
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

import torch
from transformers import (
    BertTokenizer,
    BertForSequenceClassification,
    TrainingArguments,
    Trainer,
    set_seed,
    DataCollatorWithPadding,
    EarlyStoppingCallback
)
from datasets import Dataset

# ---------------------------
# CONFIG / Defaults
# ---------------------------
DEFAULT_MODEL_NAME = "DeepPavlov/rubert-base-cased"
DEFAULT_DATA_DIR = "dataset/"
DEFAULT_OUTPUT_DIR = "models/rubert"
NUM_LABELS = 5  # 0..4
SEED = 42

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("train_rubert")

# ---------------------------
# Metrics
# ---------------------------
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=1)
    acc = accuracy_score(labels, preds)
    precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted", zero_division=0)
    return {"accuracy": acc, "precision": precision, "recall": recall, "f1": f1}


# ---------------------------
# Utility: load and prepare dataset
# ---------------------------
def load_csv_dataset(path: str, text_col: str = "text", label_col: str = "label") -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8")
    # basic cleaning
    if label_col not in df.columns or text_col not in df.columns:
        raise ValueError(f"CSV at {path} must contain columns '{text_col}' and '{label_col}'")
    df = df[[text_col, label_col]].dropna()
    df[text_col] = df[text_col].astype(str).str.strip()
    df = df[df[text_col] != ""].reset_index(drop=True)
    # ensure labels are ints
    df[label_col] = df[label_col].astype(int)
    return df


def prepare_datasets(df: pd.DataFrame, seed: int = SEED, test_size: float = 0.30, val_ratio_of_test: float = 0.5):
    # stratified split: train / temp
    train_df, temp_df = train_test_split(df, test_size=test_size, random_state=seed, stratify=df["label"])
    # temp -> val/test
    val_df, test_df = train_test_split(temp_df, test_size=val_ratio_of_test, random_state=seed, stratify=temp_df["label"])
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


# ---------------------------
# Freeze lower N layers of BERT encoder (optional)
# ---------------------------
def freeze_bert_layers(model: BertForSequenceClassification, freeze_upto_layer: int):
    """
    freeze_upto_layer: int (freeze layers with index < freeze_upto_layer)
    BERT layers are named encoder.layer.{i} in state_dict
    """
    logger.info(f"Freezing encoder layers < {freeze_upto_layer}")
    # For DeepPavlov/rubert-base-cased (BertModel) encoder layer naming is: bert.encoder.layer.{i}
    for name, param in model.named_parameters():
        # find layer index in the name if present
        if "encoder.layer." in name:
            try:
                layer_idx = int(name.split("encoder.layer.")[1].split(".")[0])
                if layer_idx < freeze_upto_layer:
                    param.requires_grad = False
                else:
                    param.requires_grad = True
            except Exception:
                # leave as is
                pass
        else:
            # keep embeddings frozen if user asked freeze_upto_layer > 0 and name contains embeddings
            if freeze_upto_layer > 0 and ("embeddings" in name):
                param.requires_grad = False


# ---------------------------
# Main training function
# ---------------------------
def train_category(
    category: str,
    csv_path: str,
    model_name: str = DEFAULT_MODEL_NAME,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    epochs: int = 3,
    batch_size: int = 8,
    max_length: int = 256,
    seed: int = SEED,
    fp16: Optional[bool] = None,
    freeze_layers: Optional[int] = None,
    learning_rate: float = 2e-5,
    weight_decay: float = 0.01,
    logging_steps: int = 50,
    eval_steps: Optional[int] = None,
    save_total_limit: int = 3,
    early_stop_patience: int = 2
):
    set_seed(seed)
    os.makedirs(output_dir, exist_ok=True)
    out_cat_dir = os.path.join(output_dir, category)
    os.makedirs(out_cat_dir, exist_ok=True)

    logger.info(f"Loading CSV for category '{category}' from {csv_path}")
    df = load_csv_dataset(csv_path)
    logger.info("Class distribution:\n%s", df["label"].value_counts().sort_index().to_dict())

    train_df, val_df, test_df = prepare_datasets(df, seed=seed)
    logger.info("Sizes — train: %d, val: %d, test: %d", len(train_df), len(val_df), len(test_df))

    # Prepare HF datasets
    train_ds = Dataset.from_pandas(train_df)
    val_ds = Dataset.from_pandas(val_df)
    test_ds = Dataset.from_pandas(test_df)

    logger.info("Loading tokenizer and model: %s", model_name)
    tokenizer = BertTokenizer.from_pretrained(model_name, use_fast=True)
    model = BertForSequenceClassification.from_pretrained(
        model_name,
        num_labels=NUM_LABELS,
        id2label={i: str(i) for i in range(NUM_LABELS)},
        label2id={str(i): i for i in range(NUM_LABELS)}
    )

    # Optional freezing
    if freeze_layers is not None and freeze_layers > 0:
        freeze_bert_layers(model, freeze_layers)

    # Tokenize function (no return_tensors)
    def tokenize_function(batch):
        return tokenizer(batch["text"], truncation=True, max_length=max_length, padding=False)

    train_ds = train_ds.map(tokenize_function, batched=True, remove_columns=[c for c in train_ds.column_names if c not in ("text", "label")])
    val_ds = val_ds.map(tokenize_function, batched=True, remove_columns=[c for c in val_ds.column_names if c not in ("text", "label")])
    test_ds = test_ds.map(tokenize_function, batched=True, remove_columns=[c for c in test_ds.column_names if c not in ("text", "label")])

    # rename label -> labels for Trainer compatibility
    train_ds = train_ds.rename_column("label", "labels")
    val_ds = val_ds.rename_column("label", "labels")
    test_ds = test_ds.rename_column("label", "labels")

    # set torch format
    train_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    val_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])
    test_ds.set_format(type="torch", columns=["input_ids", "attention_mask", "labels"])

    # Data collator with dynamic padding
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)

    # Training args
    if fp16 is None:
        fp16 = torch.cuda.is_available()

    if eval_steps is None:
        # evaluate each epoch (Trainer will do epoch based)
        eval_steps = None

    training_args = TrainingArguments(
        output_dir=out_cat_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=learning_rate,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        num_train_epochs=epochs,
        weight_decay=weight_decay,
        logging_dir=os.path.join(out_cat_dir, "logs"),
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        greater_is_better=True,
        save_total_limit=save_total_limit,
        logging_steps=logging_steps,
        fp16=fp16,
        gradient_accumulation_steps=1,
        max_grad_norm=1.0,  
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=early_stop_patience)]
    )

    # Train
    logger.info("Starting training for category '%s' ...", category)
    trainer.train()

    # Save best + final
    logger.info("Saving model to %s", out_cat_dir)
    trainer.save_model(os.path.join(out_cat_dir, "final"))
    tokenizer.save_pretrained(os.path.join(out_cat_dir, "final"))

    # Evaluate on test set
    logger.info("Evaluating on test set...")
    test_metrics = trainer.evaluate(eval_dataset=test_ds)
    logger.info("Test metrics: %s", test_metrics)

    # Confusion matrix + detailed metrics
    logger.info("Computing predictions for test set (to build confusion matrix)...")
    preds_output = trainer.predict(test_ds)
    logits = preds_output.predictions
    preds = np.argmax(logits, axis=1)
    labels = preds_output.label_ids

    cm = confusion_matrix(labels, preds)
    cm_df = pd.DataFrame(cm, index=[f"gold_{i}" for i in range(NUM_LABELS)], columns=[f"pred_{i}" for i in range(NUM_LABELS)])
    cm_csv = os.path.join(out_cat_dir, "confusion_matrix.csv")
    cm_df.to_csv(cm_csv, index=True, encoding="utf-8-sig")
    logger.info("Saved confusion matrix to %s", cm_csv)

    # Save test metrics to file
    metrics_file = os.path.join(out_cat_dir, "test_metrics.json")
    with open(metrics_file, "w", encoding="utf-8") as fh:
        json.dump(test_metrics, fh, ensure_ascii=False, indent=2)
    logger.info("Saved test metrics to %s", metrics_file)

    # Also save a small report
    report = {
        "category": category,
        "train_size": len(train_ds),
        "val_size": len(val_ds),
        "test_size": len(test_ds),
        "test_metrics": test_metrics
    }
    with open(os.path.join(out_cat_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    return trainer, test_metrics


# ---------------------------
# CLI
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Train RuBERT classifiers per category.")
    parser.add_argument("--category", type=str, help="Category name (csv must be at DATA_DIR/{category}_dataset.csv)")
    parser.add_argument("--all", action="store_true", help="Train all categories found in DATA_DIR (files ending with _dataset.csv)")
    parser.add_argument("--model_name", type=str, default=DEFAULT_MODEL_NAME)
    parser.add_argument("--data_dir", type=str, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output_dir", type=str, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=8)
    parser.add_argument("--max_length", type=int, default=256)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--fp16", action="store_true", help="Force fp16 (only if GPU available)")
    parser.add_argument("--freeze_layers", type=int, default=0, help="Freeze encoder layers < N (0 = no freeze)")
    parser.add_argument("--learning_rate", type=float, default=2e-5)
    parser.add_argument("--weight_decay", type=float, default=0.01)
    parser.add_argument("--logging_steps", type=int, default=50)
    parser.add_argument("--save_total_limit", type=int, default=3)
    parser.add_argument("--early_stop_patience", type=int, default=2)

    args = parser.parse_args()

    set_seed(args.seed)

    if args.all:
        # find all *_dataset.csv in data_dir
        files = [f for f in os.listdir(args.data_dir) if f.endswith("_dataset.csv")]
        categories = [f.replace("_dataset.csv", "") for f in files]
    else:
        if not args.category:
            raise ValueError("Either --category or --all must be specified")
        categories = [args.category]

    for cat in categories:
        csv_path = os.path.join(args.data_dir, f"{cat}_dataset.csv")
        if not os.path.exists(csv_path):
            logger.error("Dataset not found: %s. Skipping category %s", csv_path, cat)
            continue
        try:
            logger.info("=== Training category: %s ===", cat)
            trainer, metrics = train_category(
                category=cat,
                csv_path=csv_path,
                model_name=args.model_name,
                output_dir=args.output_dir,
                epochs=args.epochs,
                batch_size=args.batch_size,
                max_length=args.max_length,
                seed=args.seed,
                fp16=args.fp16,
                freeze_layers=args.freeze_layers if args.freeze_layers > 0 else None,
                learning_rate=args.learning_rate,
                weight_decay=args.weight_decay,
                logging_steps=args.logging_steps,
                save_total_limit=args.save_total_limit,
                early_stop_patience=args.early_stop_patience
            )
            logger.info("✅ Finished training %s. Test metrics: %s", cat, metrics)
        except Exception as e:
            logger.exception("❌ Error training %s: %s", cat, e)


if __name__ == "__main__":
    main()
