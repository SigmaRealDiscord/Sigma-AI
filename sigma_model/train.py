from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import torch
from torch.optim import AdamW

from sigma_model.config import SigmaConfig
from sigma_model.model import SigmaModel
from sigma_model.tokenizer import EOS, SigmaTokenizer


def load_corpus(folder: Path, max_bytes: int) -> torch.Tensor:
    paths = sorted(folder.rglob("*.txt"))
    if not paths:
        raise SystemExit(f"No .txt training files found in {folder}")
    chunks = []
    total = 0
    for path in paths:
        raw = path.read_bytes()
        if not raw:
            continue
        remaining = max_bytes - total
        if remaining <= 0:
            break
        raw = raw[:remaining]
        chunks.extend(raw)
        chunks.append(EOS)
        total += len(raw) + 1
    if total < 2048:
        raise SystemExit("Training corpus is too small; add at least a few KB of clean text.")
    print(f"Loaded {total:,} tokens from {len(paths)} text files")
    return torch.tensor(chunks, dtype=torch.long)


def main():
    parser = argparse.ArgumentParser(description="Train Sigma-0.1B from random initialization.")
    parser.add_argument("--data", default="data/train")
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--seq-len", type=int, default=512)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--max-bytes", type=int, default=100_000_000)
    parser.add_argument("--output", default="artifacts/sigma-0.1b.pt")
    args = parser.parse_args()

    random.seed(42)
    torch.manual_seed(42)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    config = SigmaConfig(max_seq_len=args.seq_len)
    tokenizer = SigmaTokenizer()
    corpus = load_corpus(Path(args.data), args.max_bytes)
    if corpus.numel() <= args.seq_len + 1:
        raise SystemExit("Corpus must be longer than the sequence length.")

    model = SigmaModel(config).to(device)
    parameter_count = sum(p.numel() for p in model.parameters())
    print(f"Training Sigma-0.1B | parameters={parameter_count:,} | device={device}")
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=0.1)
    model.train()

    for step in range(1, args.steps + 1):
        starts = torch.randint(0, corpus.numel() - args.seq_len - 1, (args.batch_size,))
        x = torch.stack([corpus[i:i + args.seq_len] for i in starts]).to(device)
        y = torch.stack([corpus[i + 1:i + args.seq_len + 1] for i in starts]).to(device)
        optimizer.zero_grad(set_to_none=True)
        _, loss = model(x, y)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        if step == 1 or step % 10 == 0:
            print(f"step {step}/{args.steps} loss={loss.item():.4f}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"config": config.to_dict(), "model": model.cpu().state_dict(), "steps": args.steps, "parameters": parameter_count}, output)
    (output.parent / "tokenizer.json").write_text(json.dumps({"type": "utf8-byte-v0", "vocab_size": tokenizer.vocab_size}, indent=2), encoding="utf-8")
    print(f"Saved checkpoint to {output}. This is a research prototype; evaluate before serving users.")


if __name__ == "__main__":
    main()
