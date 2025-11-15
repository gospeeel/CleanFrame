import pandas as pd
from torch.utils.data import Dataset
from transformers import AutoTokenizer

class RubertDataset(Dataset):
    def __init__(self, csv_path, tokenizer_name="DeepPavlov/rubert-base-cased", max_len=128):
        self.data = pd.read_csv(csv_path)
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.max_len = max_len

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        text = str(self.data.iloc[idx]["text"])
        label = int(self.data.iloc[idx]["level"])
        inputs = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt"
        )
        return {
            "input_ids": inputs["input_ids"].squeeze(),
            "attention_mask": inputs["attention_mask"].squeeze(),
            "labels": label
        }
