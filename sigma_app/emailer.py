from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from html import escape


def _setting(*names: str, default: str = "") -> str:
    """Return the first non-empty environment variable from the supplied names."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


def send_verification_email(email: str, username: str, verify_url: str) -> None:
    # Gmail SMTP: implicit TLS on 465, STARTTLS on 587.
    # Support common aliases so existing Render secrets can be reused.
    host = _setting("SMTP_HOST", default="smtp.gmail.com")
    port = int(_setting("SMTP_PORT", default="465"))
    user = _setting("SMTP_USER", "SMTP_EMAIL", "GMAIL_USER", "GMAIL_EMAIL")
    password = _setting("SMTP_PASSWORD", "GMAIL_APP_PASSWORD", "GMAIL_PASSWORD")
    sender = _setting("SMTP_FROM", "SMTP_SENDER", "SMTP_EMAIL", "GMAIL_EMAIL", default=user)

    if not all((host, user, password, sender)):
        raise RuntimeError(
            "Email delivery is not configured. Set SMTP_USER (or SMTP_EMAIL), "
            "SMTP_PASSWORD (or GMAIL_APP_PASSWORD), and optionally SMTP_HOST, "
            "SMTP_PORT and SMTP_FROM."
        )

    safe_name = escape(username)
    safe_url = escape(verify_url, quote=True)
    message = EmailMessage()
    message["Subject"] = "Verify your email — Sigma AI"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"Hey {username},\n\nThanks for registering for an account on Sigma AI! "
        f"Before we get started, we just need to confirm that this is you.\n\n"
        f"Verify your email: {verify_url}\n\n"
        "Need help? Contact our support team or reach us on Discord: @therealsigmaroblox\n\n"
        "— Sigma AI Team"
    )
    message.add_alternative(
        f"""<!doctype html><html><body style="font-family:Arial,sans-serif;color:#202124">
        <h2>Hey {safe_name},</h2>
        <p>Thanks for registering for an account on Sigma AI!</p>
        <p>Before we get started, we just need to confirm that this is you.</p>
        <p><a href="{safe_url}" style="display:inline-block;background:#1677ff;color:white;padding:12px 22px;border-radius:7px;text-decoration:none;font-weight:bold">Verify Email</a></p>
        <p>If the button does not work, copy this link into your browser:<br>{safe_url}</p>
        <p>Need help? Contact our support team or reach us on Discord: @therealsigmaroblox</p>
        <p>— Sigma AI Team</p></body></html>""",
        subtype="html",
    )

    tls_context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=20, context=tls_context) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            smtp.starttls(context=tls_context)
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(message)
