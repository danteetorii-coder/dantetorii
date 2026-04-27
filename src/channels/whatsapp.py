"""
Adaptador de canal: WhatsApp

Simula o recebimento de mensagens via WhatsApp.
Em produção, integrar com WhatsApp Business API (Meta) ou Twilio.
"""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class WhatsAppMessage:
    sender_name: str
    sender_number: str
    message_text: str
    timestamp: Optional[str] = None

    def extract_info(self) -> dict:
        """Extrai informações básicas da mensagem."""
        info = {
            "name": self.sender_name,
            "whatsapp": self.sender_number,
            "message": self.message_text,
        }

        # Detecta CNPJ
        cnpj_pattern = r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}"
        cnpj_match = re.search(cnpj_pattern, self.message_text)
        if cnpj_match:
            info["cnpj"] = cnpj_match.group()

        # Detecta email
        email_pattern = r"[\w.-]+@[\w.-]+\.\w+"
        email_match = re.search(email_pattern, self.message_text)
        if email_match:
            info["email"] = email_match.group()

        # Detecta número de funcionários/vidas
        lives_pattern = r"(\d+)\s*(funcionários?|vidas?|colaboradores?|pessoas?)"
        lives_match = re.search(lives_pattern, self.message_text, re.IGNORECASE)
        if lives_match:
            info["num_beneficiaries"] = int(lives_match.group(1))

        return info

    def to_raw_text(self) -> str:
        return (
            f"Mensagem WhatsApp de {self.sender_name} ({self.sender_number}):\n"
            f"{self.message_text}"
        )


class WhatsAppChannel:
    """Adaptador para processar mensagens do WhatsApp."""

    CHANNEL_NAME = "whatsapp"

    def parse_message(self, raw_data: dict) -> WhatsAppMessage:
        """Parse mensagem no formato padrão da WhatsApp Business API."""
        return WhatsAppMessage(
            sender_name=raw_data.get("profile_name", raw_data.get("name", "Desconhecido")),
            sender_number=raw_data.get("from", raw_data.get("number", "")),
            message_text=raw_data.get("text", raw_data.get("body", raw_data.get("message", ""))),
            timestamp=raw_data.get("timestamp"),
        )

    def format_for_agent(self, message: WhatsAppMessage) -> str:
        return f"[WhatsApp]\n{message.to_raw_text()}"

    def format_outbound_message(self, text: str) -> dict:
        """Formata mensagem para envio via WhatsApp Business API."""
        return {
            "type": "text",
            "text": {"body": text},
        }
