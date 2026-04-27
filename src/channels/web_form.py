"""
Adaptador de canal: Formulário Web

Simula o recebimento de leads vindos de landing pages e formulários de contato.
Em produção, este módulo receberia webhooks do formulário ou CRM.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WebFormSubmission:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    num_employees: Optional[int] = None
    message: Optional[str] = None
    plan_interest: Optional[str] = None
    utm_source: Optional[str] = None
    utm_campaign: Optional[str] = None

    def to_raw_text(self) -> str:
        parts = [f"Nome: {self.name}"]
        if self.email:
            parts.append(f"Email: {self.email}")
        if self.phone:
            parts.append(f"Telefone: {self.phone}")
        if self.company_name:
            parts.append(f"Empresa: {self.company_name}")
        if self.num_employees:
            parts.append(f"Número de funcionários: {self.num_employees}")
        if self.plan_interest:
            parts.append(f"Interesse: {self.plan_interest}")
        if self.message:
            parts.append(f"Mensagem: {self.message}")
        if self.utm_source:
            parts.append(f"Origem: {self.utm_source} / {self.utm_campaign or 'sem campanha'}")
        return "\n".join(parts)


class WebFormChannel:
    """Adaptador para processar submissões de formulários web."""

    CHANNEL_NAME = "formulario_web"

    def parse_submission(self, form_data: dict) -> WebFormSubmission:
        return WebFormSubmission(
            name=form_data.get("name", form_data.get("nome", "Desconhecido")),
            email=form_data.get("email"),
            phone=form_data.get("phone", form_data.get("telefone")),
            company_name=form_data.get("company", form_data.get("empresa")),
            num_employees=form_data.get("num_employees", form_data.get("funcionarios")),
            message=form_data.get("message", form_data.get("mensagem")),
            plan_interest=form_data.get("plan_interest", form_data.get("interesse")),
            utm_source=form_data.get("utm_source"),
            utm_campaign=form_data.get("utm_campaign"),
        )

    def format_for_agent(self, submission: WebFormSubmission) -> str:
        return f"[Formulário Web]\n{submission.to_raw_text()}"
