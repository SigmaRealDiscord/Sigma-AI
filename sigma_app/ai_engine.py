from __future__ import annotations

import os
from pathlib import Path

import torch

from sigma_model.config import SigmaConfig
from sigma_model.model import SigmaModel
from sigma_model.tokenizer import BOS, SigmaTokenizer


_model = None
_tokenizer = None


def _load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer
    checkpoint_path = Path(os.getenv("SIGMA_MODEL_CHECKPOINT", "artifacts/sigma-0.1b.pt"))
    if not checkpoint_path.is_file():
        raise RuntimeError("Sigma-0.1B has not been trained yet. No checkpoint was found.")
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    config = SigmaConfig(**checkpoint["config"])
    model = SigmaModel(config)
    model.load_state_dict(checkpoint["model"])
    model.eval()
    _model = model
    _tokenizer = SigmaTokenizer()
    return _model, _tokenizer


def generate_text(messages: list[dict], system_prompt: str = "You are Sigma AI.", max_new_tokens: int = 240) -> str:
    model, tokenizer = _load_model()
    parts = ["System: " + system_prompt]
    for item in messages[-20:]:
        role = str(item.get("role", "user")).capitalize()
        content = item.get("content", "")
        if isinstance(content, list):
            content = " ".join(str(p.get("text", "")) for p in content if isinstance(p, dict) and p.get("type") == "text")
        parts.append(role + ": " + str(content))
    parts.append("Assistant:")
    prompt = "\n".join(parts)
    ids = tokenizer.encode(prompt, add_special_tokens=False)
    input_ids = torch.tensor([[BOS] + ids[-(model.config.max_seq_len - 1):]], dtype=torch.long)
    with torch.inference_mode():
        output = model.generate(input_ids, max_new_tokens=max_new_tokens)
    answer_ids = output[0, input_ids.shape[1]:].tolist()
    answer = tokenizer.decode(answer_ids).strip()
    if not answer:
        raise RuntimeError("Sigma-0.1B returned an empty response.")
    return answer
