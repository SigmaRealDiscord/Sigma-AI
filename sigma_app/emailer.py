from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape


def send_verification_email(email: str, username: str, verify_url: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", user).strip()
    if not all((host, user, password, sender)):
        raise RuntimeError("Email delivery is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM.")

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
    with smtplib.SMTP(host, port, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(message)
