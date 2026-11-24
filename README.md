# Sigma AI

Sigma AI is a standalone, text-only assistant application. The repository also contains the separate Sigma Developers portal and the original Sigma-0.1B model training code.

## Project structure

- `main.py` — FastAPI application and chat history.
- `sigma_app/` — account registration, email verification, chat history, memory, Developer portal, API-key management.
- `sigma_model/` — custom decoder-only Transformer, UTF-8 byte tokenizer, and from-scratch training script.
- `sigma_app/developers.html` — separate Sigma Developers web portal at `/developers`.

## Sigma-0.1B status

The model code is a **from-scratch training prototype**, not a finished or trained assistant. It initializes random weights and does not download or call Gemini, OpenAI, Qwen, Llama, or another pretrained model. A model checkpoint must be trained and deployed before chat or API inference can work.

The initial tokenizer is a custom UTF-8 byte tokenizer. It can encode all Unicode scripts, but it is not yet an optimized learned multilingual tokenizer. Supporting 100 languages in the tokenizer does not guarantee good language ability: that requires a large, balanced, legally usable corpus and extensive training/evaluation.

See [sigma_model/README.md](sigma_model/README.md) for training instructions.

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` for Sigma AI and `http://localhost:8000/developers` for Sigma Developers.

## Environment variables

Required for production:

- `SIGMA_AUTH_SECRET` — long random session-signing secret.
- `DATABASE_URL` — PostgreSQL connection URL; SQLite fallback is for local development only.
- `SIGMA_APP_URL` — public HTTPS URL used in email verification links.
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — email delivery.
- `COOKIE_HTTPS_ONLY=true` — secure cookies in production.
- `SIGMA_MODEL_CHECKPOINT` — optional path to the trained Sigma checkpoint; default is `artifacts/sigma-0.1b.pt`.
- `SIGMA_OWNER_EMAIL` — verified email address assigned the Owner role.
- `SIGMA_ADMIN_EMAILS` — comma-separated verified email addresses assigned Admin role.

Do not commit secrets to GitHub or put them in frontend JavaScript. Set them in the hosting provider's environment-variable settings. Owner/Admin roles are assigned server-side only after email verification; a user cannot grant themselves a role.

## Sigma API

Create an account, verify its email, then open Sigma Developers and create an API key. The raw key is displayed once; only its SHA-256 hash is stored. Users can list and revoke only their own keys.

The text-only endpoint is:

```http
POST /v1/chat/completions
Authorization: Bearer sigma_sk_live_...
Content-Type: application/json
```

Example body:

```json
{
  "model": "sigma-0.1b",
  "messages": [
    {"role": "user", "content": "Hi"}
  ]
}
```

There is no third-party AI provider key in this design. API keys authorize access to Sigma's own endpoint; they are not model weights and are not embedded in Sigma-0.1B.

## Important deployment note

A roughly 100M-parameter model needs substantial RAM and compute for inference, and training requires much more GPU compute. A normal lightweight web worker is not a training cluster. Keep the web/API service and model training/inference capacity separate if the chosen host cannot run the model. No trained weights are committed to this repository.
