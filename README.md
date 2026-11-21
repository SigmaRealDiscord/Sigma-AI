# Sigma AI

Sigma AI is a standalone, responsive web app. It is intentionally separated from the Discord bot repository and does not modify or depend on the bot.

## Included features

- Responsive English chat interface for mobile and desktop
- Email/password registration with one-time email verification
- Login/logout and signed sessions
- User-owned conversations with persistent message history
- Chat search, rename, and delete
- Image attachments and multimodal model requests
- Separate saved-memory notes (add/list/delete)
- Last 100 messages as active context
- Keyword retrieval from up to 2,000 older messages across the user's conversations

## Run locally

Python 3.11+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`. For local development, SQLite is used if `DATABASE_URL` is omitted.

## Required environment variables

- `SIGMA_AI_API_KEY` — model provider API key
- `SIGMA_AI_BASE_URL` — OpenAI-compatible API base URL
- `SIGMA_AI_MODEL` — model identifier
- `SIGMA_AUTH_SECRET` — long, random signing secret; never commit it
- `DATABASE_URL` — PostgreSQL connection URL for persistent production data
- `SIGMA_APP_URL` — public HTTPS URL used in verification links
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` — outgoing email configuration
- `COOKIE_HTTPS_ONLY` — keep `true` in production; set `false` only for local HTTP development
- `SIGMA_ALLOWED_ORIGINS` — optional comma-separated CORS allowlist if a separate frontend origin is used

Do not put secrets in source files, GitHub commits, or frontend JavaScript. Set them in the hosting provider's secret/environment-variable settings.

## Deploy

The included `Procfile` starts the FastAPI web service with the platform-provided `PORT`. Attach a persistent PostgreSQL database and configure the environment variables above before enabling public signups.

## Security and production notes

- The SQLite fallback is for development only; use managed PostgreSQL for production.
- Use a unique random `SIGMA_AUTH_SECRET` in production.
- Email verification links are single-use and expire after 30 minutes.
- Passwords are stored as PBKDF2-HMAC-SHA256 hashes.
- Restrict access to the database and keep provider credentials server-side.
- Review provider limits, image-size limits, and abuse protections before opening registration publicly.
