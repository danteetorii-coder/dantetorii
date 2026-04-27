"""
Adaptador de canal: LinkedIn

Canal principal para o nicho de executivos PJ.
Leads chegam via Lead Gen Forms em campanhas segmentadas por cargo/setor,
ou via InMail de prospecção ativa.

Segmentação de campanha recomendada:
- Cargos: Diretor, Gerente Sênior, C-level, VP, Sócio, Fundador
- Setores: Tecnologia, Consultoria, Finanças, Jurídico, Engenharia
- Comportamento: mudança de emprego recente nos últimos 90 dias
- Grupos: "Empreendedores PJ", "Consultores Independentes", etc.
"""

from dataclasses import dataclass
from typing import Optional


# Cargos que indicam perfil executivo (alta probabilidade de ser o nicho)
EXECUTIVE_TITLES = [
    "diretor", "director", "gerente sênior", "senior manager", "vp", "vice-presidente",
    "vice president", "ceo", "cto", "cfo", "coo", "cmo", "ciso", "chro",
    "head of", "head de", "sócio", "partner", "fundador", "founder", "co-founder",
    "cofundador", "presidente", "superintendent", "superintendente",
]

# Padrões de texto que indicam transição CLT → PJ
TRANSITION_SIGNALS = [
    "abri minha empresa", "abri meu cnpj", "virei pj", "me tornei pj",
    "saí da empresa", "saí do emprego", "deixei a empresa", "fui demitido",
    "pedido de demissão", "empreendendo", "consultor independente",
    "freelancer", "autônomo", "sócio fundador", "minha consultoria",
]


@dataclass
class LinkedInLead:
    full_name: str
    job_title: Optional[str] = None
    company: Optional[str] = None           # Empresa ATUAL (pode ser a PJ nova)
    previous_company: Optional[str] = None  # Empresa anterior (onde era CLT)
    company_size: Optional[str] = None      # Faixa do LinkedIn
    email: Optional[str] = None
    phone: Optional[str] = None
    message: Optional[str] = None
    profile_url: Optional[str] = None
    campaign: Optional[str] = None
    connection_degree: Optional[int] = None  # 1, 2 ou 3

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

    def is_executive_profile(self) -> bool:
        if not self.job_title:
            return False
        title_lower = self.job_title.lower()
        return any(t in title_lower for t in EXECUTIVE_TITLES)

    def has_transition_signal(self) -> bool:
        text = (self.message or "").lower()
        return any(s in text for s in TRANSITION_SIGNALS)

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
            parts.append(f"Empresa atual: {self.company}")
        if self.previous_company:
            parts.append(f"Empresa anterior: {self.previous_company}")
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
        if self.is_executive_profile():
            parts.append("[PERFIL EXECUTIVO IDENTIFICADO]")
        if self.has_transition_signal():
            parts.append("[SINAL DE TRANSIÇÃO CLT→PJ DETECTADO]")
        return "\n".join(parts)


class LinkedInChannel:
    """Adaptador para processar leads do LinkedIn."""

    CHANNEL_NAME = "linkedin"

    def parse_lead_gen_form(self, form_data: dict) -> LinkedInLead:
        """Parse de Lead Gen Form — formato padrão da API LinkedIn Marketing."""
        first = form_data.get("firstName", form_data.get("first_name", ""))
        last = form_data.get("lastName", form_data.get("last_name", ""))
        return LinkedInLead(
            full_name=f"{first} {last}".strip() or form_data.get("name", "Desconhecido"),
            job_title=form_data.get("title", form_data.get("job_title")),
            company=form_data.get("companyName", form_data.get("company")),
            company_size=form_data.get("companySizeRange", form_data.get("company_size")),
            email=form_data.get("emailAddress", form_data.get("email")),
            phone=form_data.get("phoneNumber", form_data.get("phone")),
            message=form_data.get("message"),
            campaign=form_data.get("campaignName", form_data.get("campaign")),
        )

    def parse_inmail(self, raw_data: dict) -> LinkedInLead:
        """Parse de InMail recebido."""
        return LinkedInLead(
            full_name=raw_data.get("name", "Desconhecido"),
            job_title=raw_data.get("job_title"),
            company=raw_data.get("company"),
            previous_company=raw_data.get("previous_company"),
            email=raw_data.get("email"),
            message=raw_data.get("message"),
            profile_url=raw_data.get("profile_url"),
            connection_degree=raw_data.get("connection_degree"),
        )

    def format_for_agent(self, lead: LinkedInLead) -> str:
        return f"[LinkedIn]\n{lead.to_raw_text()}"

    def get_campaign_targeting_brief(self) -> str:
        """Retorna briefing de segmentação de campanha para o nicho."""
        return """
SEGMENTAÇÃO LINKEDIN — DTS Executivos PJ

Critérios de público:
- Cargos: Diretor, Gerente Sênior, VP, C-level, Sócio, Fundador
- Setores: Tecnologia, Consultoria, Financeiro, Jurídico, Saúde Corporativa
- Seniority: Senior, Manager, Director, VP, C-Suite, Partner, Owner
- Localização: capitais e principais regiões metropolitanas do Brasil
- Comportamento: "mudou de emprego nos últimos 90 dias" (filtro LinkedIn)

Copy sugerido para Lead Gen Form:
Título: "Saiu do CLT e abriu PJ? Não perca seu plano de saúde"
Subtítulo: "Com a portabilidade da ANS, você aproveita as carências do plano anterior — mas tem apenas 60 dias."
CTA: "Quero minha cotação gratuita"

Campos do formulário:
- Nome completo (pré-preenchido)
- Email profissional (pré-preenchido)
- Cargo atual (pré-preenchido)
- Empresa atual (pré-preenchido)
- Telefone / WhatsApp
- "Quantas pessoas incluirá no plano?" (dropdown: 3, 4, 5, 6+)
- "Quando saiu da empresa?" (dropdown: menos de 30 dias, 30-60 dias, mais de 60 dias)
""".strip()
