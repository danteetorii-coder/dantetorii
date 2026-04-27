"""
Adaptador de canal: Email

Simula o recebimento de leads via email.
Em produção, integrar com Gmail API, Outlook API ou serviço IMAP.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class EmailLead:
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received_at: Optional[str] = None

    def to_raw_text(self) -> str:
        return (
            f"Email recebido de: {self.sender_name} <{self.sender_email}>\n"
            f"Assunto: {self.subject}\n"
            f"Mensagem:\n{self.body}"
        )

    def extract_phone(self) -> Optional[str]:
        pattern = r"(?:\+55\s?)?(?:\(?\d{2}\)?[\s-]?)(?:9\d{4}|\d{4})[\s-]?\d{4}"
        match = re.search(pattern, self.body)
        return match.group() if match else None

    def extract_company(self) -> Optional[str]:
        patterns = [
            r"(?:empresa|company|companhia|corporação):\s*([^\n]+)",
            r"([A-Z][a-zA-Z\s]+(?:Ltda|S\.A\.|ME|EIRELI|EPP)\.?)",
        ]
        for pattern in patterns:
            match = re.search(pattern, self.body, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None


class EmailChannel:
    """Adaptador para processar emails de leads."""

    CHANNEL_NAME = "email"

    def parse_email(self, raw_data: dict) -> EmailLead:
        return EmailLead(
            sender_name=raw_data.get("from_name", raw_data.get("name", "Desconhecido")),
            sender_email=raw_data.get("from_email", raw_data.get("email", "")),
            subject=raw_data.get("subject", "Sem assunto"),
            body=raw_data.get("body", raw_data.get("text", raw_data.get("message", ""))),
            received_at=raw_data.get("received_at", raw_data.get("date")),
        )

    def format_for_agent(self, email: EmailLead) -> str:
        return f"[Email]\n{email.to_raw_text()}"
