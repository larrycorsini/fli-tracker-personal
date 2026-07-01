"""Pluggable alert delivery for Fli-Tracker (iMessage, email)."""

from __future__ import annotations

import os
import smtplib
import subprocess
from email.message import EmailMessage
from typing import Protocol


class AlertNotifier(Protocol):
    """Send a plain-text alert message."""

    def send(self, message: str) -> None: ...


class IMessageNotifier:
    """Deliver alerts via macOS Messages (iMessage)."""

    def __init__(self, phone_number: str) -> None:
        self.phone_number = phone_number

    def send(self, message: str) -> None:
        script = """
        on run argv
            set msg to item 1 of argv
            set phone to item 2 of argv
            tell application "Messages"
                set targetService to 1st service whose service type = iMessage
                set targetBuddy to buddy phone of targetService
                send msg to targetBuddy
            end tell
        end run
        """
        subprocess.run(
            ["osascript", "-e", script, message, self.phone_number],
            check=True,
        )


class EmailNotifier:
    """Deliver alerts via SMTP (env-driven, no hardcoded credentials)."""

    def __init__(
        self,
        to_address: str,
        *,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_address: str | None = None,
    ) -> None:
        self.to_address = to_address
        self.smtp_host = smtp_host or os.environ.get("FLI_SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.environ.get("FLI_SMTP_PORT", "587"))
        self.smtp_user = smtp_user or os.environ.get("FLI_SMTP_USER", "")
        self.smtp_password = smtp_password or os.environ.get("FLI_SMTP_PASSWORD", "")
        self.from_address = from_address or os.environ.get("FLI_ALERT_FROM", self.smtp_user or to_address)

    def send(self, message: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = "Fli-Tracker deal alert"
        msg["From"] = self.from_address
        msg["To"] = self.to_address
        msg.set_content(message)
        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
            server.starttls()
            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)


def build_notifiers() -> list[AlertNotifier]:
    """Construct notifiers from environment (phone and/or email)."""
    notifiers: list[AlertNotifier] = []
    phone = os.environ.get("FLI_ALERT_PHONE", "").strip()
    if phone:
        notifiers.append(IMessageNotifier(phone))
    email = os.environ.get("FLI_ALERT_EMAIL", "").strip()
    if email:
        notifiers.append(EmailNotifier(email))
    return notifiers


def dispatch_alert(message: str) -> list[str]:
    """Send message through all configured notifiers; return channels used."""
    notifiers = build_notifiers()
    if not notifiers:
        return []
    channels: list[str] = []
    for notifier in notifiers:
        notifier.send(message)
        if isinstance(notifier, IMessageNotifier):
            channels.append("imessage")
        elif isinstance(notifier, EmailNotifier):
            channels.append("email")
    return channels
