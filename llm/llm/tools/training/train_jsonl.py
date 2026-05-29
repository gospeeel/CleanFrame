import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from safetensors.torch import save_file
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.utils.class_weight import compute_class_weight
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm
from transformers import AutoModel, AutoTokenizer, get_linear_schedule_with_warmup

from llm.rating import RATING_ORDER, RATING_TO_ID


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for field in ("text", "category", "level", "rating"):
                if field not in row:
                    raise ValueError(f"{path}:{line_no}: missing {field}")
            row["level"] = int(row["level"])
            rows.append(row)
    if not rows:
        raise ValueError(f"Dataset is empty: {path}")
    return rows


class RatingJsonlDataset(Dataset):
    def __init__(self, rows, tokenizer, category_to_id, level_to_id, rating_to_id, max_len):
        self.rows = rows
        self.tokenizer = tokenizer
        self.category_to_id = category_to_id
        self.level_to_id = level_to_id
        self.rating_to_id = rating_to_id
        self.max_len = max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        encoded = self.tokenizer(
            row["text"],
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": encoded["input_ids"].squeeze(0),
            "attention_mask": encoded["attention_mask"].squeeze(0),
            "category": torch.tensor(self.category_to_id[row["category"]], dtype=torch.long),
            "level": torch.tensor(self.level_to_id[int(row["level"])], dtype=torch.long),
            "rating": torch.tensor(self.rating_to_id[row["rating"]], dtype=torch.long),
        }


class MultiTaskRatingModel(nn.Module):
    def __init__(self, base_model, num_categories, num_levels, num_ratings, dropout=0.3):
        super().__init__()
        self.bert = AutoModel.from_pretrained(base_model)
        hidden_size = self.bert.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.category_head = nn.Linear(hidden_size, num_categories)
        self.level_head = nn.Linear(hidden_size, num_levels)
        self.rating_head = nn.Linear(hidden_size, num_ratings)

    def forward(self, input_ids, attention_mask):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        pooled = self.dropout(outputs.pooler_output)
        return {
            "category": self.category_head(pooled),
            "level": self.level_head(pooled),
            "rating": self.rating_head(pooled),
        }


def class_weights(values: list[int], num_classes: int) -> torch.Tensor:
    classes = np.arange(num_classes)
    weights = compute_class_weight(class_weight="balanced", classes=classes, y=np.array(values))
    return torch.tensor(weights.astype(np.float32), dtype=torch.float32)


def evaluate_model(model, dataloader, device):
    model.eval()
    y_true = {"category": [], "level": [], "rating": []}
    y_pred = {"category": [], "level": [], "rating": []}

    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            for key in y_true:
                y_true[key].extend(batch[key].cpu().numpy().tolist())
                y_pred[key].extend(outputs[key].argmax(dim=1).cpu().numpy().tolist())

    return {
        "category_accuracy": accuracy_score(y_true["category"], y_pred["category"]),
        "category_macro_f1": f1_score(y_true["category"], y_pred["category"], average="macro", zero_division=0),
        "level_accuracy": accuracy_score(y_true["level"], y_pred["level"]),
        "level_macro_f1": f1_score(y_true["level"], y_pred["level"], average="macro", zero_division=0),
        "level_mae": mean_absolute_error(y_true["level"], y_pred["level"]),
        "rating_accuracy": accuracy_score(y_true["rating"], y_pred["rating"]),
        "rating_macro_f1": f1_score(y_true["rating"], y_pred["rating"], average="macro", zero_division=0),
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def train(args):
    train_rows = read_jsonl(args.train)
    validation_rows = read_jsonl(args.validation)

    categories = sorted({row["category"] for row in train_rows + validation_rows})
    levels = sorted({int(row["level"]) for row in train_rows + validation_rows})
    category_to_id = {category: index for index, category in enumerate(categories)}
    id_to_category = {index: category for category, index in category_to_id.items()}
    level_to_id = {level: index for index, level in enumerate(levels)}
    id_to_level = {index: level for level, index in level_to_id.items()}
    rating_to_id = {rating: RATING_TO_ID[rating] for rating in RATING_ORDER}
    id_to_rating = {index: rating for rating, index in rating_to_id.items()}

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    train_dataset = RatingJsonlDataset(train_rows, tokenizer, category_to_id, level_to_id, rating_to_id, args.max_len)
    validation_dataset = RatingJsonlDataset(validation_rows, tokenizer, category_to_id, level_to_id, rating_to_id, args.max_len)
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size)

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = MultiTaskRatingModel(
        base_model=args.base_model,
        num_categories=len(category_to_id),
        num_levels=len(level_to_id),
        num_ratings=len(rating_to_id),
        dropout=args.dropout,
    ).to(device)

    category_weights = class_weights([category_to_id[row["category"]] for row in train_rows], len(category_to_id)).to(device)
    level_weights = class_weights([level_to_id[int(row["level"])] for row in train_rows], len(level_to_id)).to(device)
    rating_weights = class_weights([rating_to_id[row["rating"]] for row in train_rows], len(rating_to_id)).to(device)

    loss_fns = {
        "category": nn.CrossEntropyLoss(weight=category_weights),
        "level": nn.CrossEntropyLoss(weight=level_weights),
        "rating": nn.CrossEntropyLoss(weight=rating_weights),
    }
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    total_steps = len(train_loader) * args.epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=min(args.warmup_steps, max(0, total_steps // 10)),
        num_training_steps=total_steps,
    )

    best_metric = -1.0
    best_state = None
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in tqdm(train_loader, desc=f"epoch {epoch}/{args.epochs}"):
            optimizer.zero_grad(set_to_none=True)
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            loss = (
                args.category_loss_weight * loss_fns["category"](outputs["category"], batch["category"].to(device))
                + args.level_loss_weight * loss_fns["level"](outputs["level"], batch["level"].to(device))
                + args.rating_loss_weight * loss_fns["rating"](outputs["rating"], batch["rating"].to(device))
            )
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            scheduler.step()
            losses.append(float(loss.detach().cpu()))

        metrics = evaluate_model(model, validation_loader, device)
        metrics["train_loss"] = float(np.mean(losses))
        metrics["epoch"] = epoch
        history.append(metrics)
        score = metrics["rating_macro_f1"] + metrics["category_macro_f1"] + metrics["level_macro_f1"]
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        if score > best_metric:
            best_metric = score
            best_state = {key: value.detach().cpu().contiguous() for key, value in model.state_dict().items()}

    if best_state is not None:
        model.load_state_dict(best_state)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(args.output_dir)
    model.bert.config.save_pretrained(args.output_dir)
    save_file(
        {key: value.detach().cpu().contiguous() for key, value in model.state_dict().items()},
        args.output_dir / "model.safetensors",
        metadata={"format": "pt"},
    )
    (args.output_dir / "category_to_id.json").write_text(json.dumps(category_to_id, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "id_to_category.json").write_text(json.dumps(id_to_category, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "level_to_id.json").write_text(json.dumps(level_to_id, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "id_to_level.json").write_text(json.dumps(id_to_level, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "rating_to_id.json").write_text(json.dumps(rating_to_id, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "id_to_rating.json").write_text(json.dumps(id_to_rating, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    np.save(args.output_dir / "level_class_weights.npy", level_weights.detach().cpu().numpy())
    np.save(args.output_dir / "level_shift.npy", np.array(min(levels)))

    manifest = {
        "schema_version": 2,
        "model_name": args.model_name,
        "base_model": args.base_model,
        "task": "script_age_rating_risk_detection",
        "categories": category_to_id,
        "ratings": rating_to_id,
        "levels": level_to_id,
        "max_len": args.max_len,
        "framework": {
            "torch": torch.__version__,
            "weights_format": "safetensors",
        },
        "training": {
            "train": str(args.train),
            "validation": str(args.validation),
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "history": history,
        },
        "weights": {
            "file": "model.safetensors",
            "bytes": (args.output_dir / "model.safetensors").stat().st_size,
            "sha256": sha256(args.output_dir / "model.safetensors"),
        },
        "created_at_unix": int(time.time()),
    }
    (args.output_dir / "model_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output_dir": str(args.output_dir), "best_score": best_metric}, ensure_ascii=False, indent=2))


def parse_args():
    parser = argparse.ArgumentParser(description="Train ML_WINK multitask age-rating model from JSONL datasets.")
    parser.add_argument("--train", type=Path, required=True)
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("trained_model_candidate"))
    parser.add_argument("--base-model", default="DeepPavlov/rubert-base-cased")
    parser.add_argument("--model-name", default="ml-wink-rubert-multitask")
    parser.add_argument("--max-len", type=int, default=256)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--warmup-steps", type=int, default=100)
    parser.add_argument("--dropout", type=float, default=0.3)
    parser.add_argument("--max-grad-norm", type=float, default=1.0)
    parser.add_argument("--category-loss-weight", type=float, default=1.0)
    parser.add_argument("--level-loss-weight", type=float, default=1.0)
    parser.add_argument("--rating-loss-weight", type=float, default=1.2)
    parser.add_argument("--device", default=None)
    return parser.parse_args()


def main():
    train(parse_args())


if __name__ == "__main__":
    main()
