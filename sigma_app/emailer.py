from __future__ import annotations

import os
import requests


def send_verification_email(email: str, username: str, verify_url: str) -> None:
    """Send the verification email through the Google Apps Script HTTPS endpoint."""
    script_url = os.environ["GOOGLE_SCRIPT_URL"]
    secret = os.environ["GOOGLE_SECRET_KEY"]

    subject = "Verify your email — Sigma AI"
    body = (
        f"Hey {username},\n\n"
        "Thanks for registering for an account on Sigma AI! "
        "Before we get started, we just need to confirm that this is you.\n\n"
        f"Verify your email: {verify_url}\n\n"
        "Need help? Contact our support team or reach us on Discord: @therealsigmaroblox\n\n"
        "— Sigma AI Team"
    )

    payload = {
        "secret": secret,
        "to": email,
        "subject": subject,
        "body": body,
    }

    # Apps Script web apps may redirect their ContentService response.
    # requests follows the redirect; the initial POST (including its JSON body)
    # is sent to the script endpoint before the redirected response is fetched.
    response = requests.post(
        script_url,
        json=payload,
        timeout=30,
        allow_redirects=True,
    )
    response.raise_for_status()

    # If the Apps Script returns JSON, respect an explicit application-level
    # failure instead of treating an HTTP 200 as successful delivery.
    try:
        result = response.json()
    except ValueError:
        result = None

    if isinstance(result, dict) and result.get("ok") is False:
        raise RuntimeError("Google Apps Script reported that the verification email could not be sent.")
