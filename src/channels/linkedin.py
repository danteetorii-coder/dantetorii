"""
Adaptador de canal: LinkedIn

Simula o recebimento de leads via LinkedIn (InMail, formulários Lead Gen, etc.).
Em produção, integrar com LinkedIn Marketing Solutions API.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LinkedInLead:
    full_name: str
    job_title: Optional[str] = None
    company: Optional[str] = None
    company_size: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    profile_url: Optional[str] = None
    campaign: Optional[str] = None

    # Tamanhos de empresa do LinkedIn
    SIZE_MAP = {
        "1-10": 5,
        "11-50": 30,
        "51-200": 100,
        "201-500": 350,
        "501-1000": 750,
        "1001-5000": 3000,
        "5001-10000": 7500,
        "10001+": 15000,
    }

    def estimate_company_size(self) -> Optional[int]:
        if not self.company_size:
            return None
        for key, value in self.SIZE_MAP.items():
            if key in self.company_size:
                return value
        return None

    def to_raw_text(self) -> str:
        parts = [f"Lead LinkedIn: {self.full_name}"]
        if self.job_title:
            parts.append(f"Cargo: {self.job_title}")
        if self.company:
            parts.append(f"Empresa: {self.company}")
        if self.company_size:
            parts.append(f"Tamanho da empresa: {self.company_size}")
        if self.email:
            parts.append(f"Email: {self.email}")
        if self.phone:
            parts.append(f"Telefone: {self.phone}")
        if self.message:
            parts.append(f"Mensagem: {self.message}")
        if self.campaign:
            parts.append(f"Campanha: {self.campaign}")
        return "\n".join(parts)


class LinkedInChannel:
    """Adaptador para processar leads do LinkedIn."""

    CHANNEL_NAME = "linkedin"

    def parse_lead_gen_form(self, form_data: dict) -> LinkedInLead:
        """Parse de Lead Gen Form do LinkedIn."""
        return LinkedInLead(
            full_name=form_data.get("firstName", "") + " " + form_data.get("lastName", ""),
            job_title=form_data.get("title"),
            company=form_data.get("companyName"),
            company_size=form_data.get("companySizeRange"),
            email=form_data.get("emailAddress"),
            phone=form_data.get("phoneNumber"),
            message=form_data.get("message"),
            campaign=form_data.get("campaignName"),
        )

    def parse_inmail(self, raw_data: dict) -> LinkedInLead:
        """Parse de InMail recebido."""
        return LinkedInLead(
            full_name=raw_data.get("name", "Desconhecido"),
            job_title=raw_data.get("job_title"),
            company=raw_data.get("company"),
            email=raw_data.get("email"),
            message=raw_data.get("message"),
            profile_url=raw_data.get("profile_url"),
        )

    def format_for_agent(self, lead: LinkedInLead) -> str:
        return f"[LinkedIn]\n{lead.to_raw_text()}"
