# Sigma-0.1B

Sigma-0.1B is the planned original text-only language model for Sigma AI. The implementation here is a **training prototype**, not a trained assistant yet.

## Independence

- The Transformer is initialized randomly by this repository's code.
- No third-party pretrained model or pretrained weights are downloaded.
- The tokenizer is a local UTF-8 byte tokenizer; it can represent text from any language, but is less token-efficient than a learned multilingual tokenizer.
- Training data must be supplied by the project owner and must be legally usable. Do not commit private, copyrighted, or personal data to the repository.

## Prepare data

Put clean, permissioned `.txt` files under `data/train/`. Keep a record of each source, language, license, and processing method. Balance languages deliberately; merely including 100 languages does not make model quality equal across them.

## Install training dependencies

```bash
pip install -r requirements-training.txt
```

## Train from scratch

```bash
python -m sigma_model.train --data data/train --steps 1000 --batch-size 2 --seq-len 512
```

The first run initializes random weights. It does not resume or import another model. The default checkpoint is written to `artifacts/sigma-0.1b.pt`; checkpoints are intentionally excluded from Git.

## Important limitations

This starter has a byte tokenizer and a basic decoder-only Transformer. It is not yet instruction-tuned, evaluated, safety-tuned, or competitive with large assistant models. A 100M-parameter model trained on a small corpus will produce poor results. Training requires substantial compute; a free web worker is not a substitute for GPU training. Start with a small experiment, verify loss decreases, then plan a properly licensed multilingual corpus and GPU budget.
