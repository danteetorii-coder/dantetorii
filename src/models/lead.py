from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class LeadStatus(str, Enum):
    NEW = "novo"
    QUALIFYING = "qualificando"
    QUALIFIED = "qualificado"
    DISQUALIFIED = "desqualificado"
    CONTACTED = "contatado"
    NEGOTIATING = "negociando"
    CONVERTED = "convertido"
    LOST = "perdido"


class LeadChannel(str, Enum):
    WHATSAPP = "whatsapp"
    LINKEDIN = "linkedin"
    WEB_FORM = "formulario_web"
    EMAIL = "email"
    PHONE = "telefone"
    REFERRAL = "indicacao"
    MANUAL = "manual"


class PlanType(str, Enum):
    INDIVIDUAL = "individual"
    FAMILY = "familiar"
    SME = "pme"           # Pequena e Média Empresa
    CORPORATE = "empresarial"
    DENTAL = "odontologico"
    UNKNOWN = "desconhecido"


@dataclass
class Lead:
    id: str
    name: str
    channel: LeadChannel
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    status: LeadStatus = LeadStatus.NEW

    # Contato
    phone: Optional[str] = None
    email: Optional[str] = None
    whatsapp: Optional[str] = None

    # Dados da empresa (para planos PJ)
    company_name: Optional[str] = None
    company_size: Optional[int] = None         # número de funcionários
    cnpj: Optional[str] = None
    segment: Optional[str] = None              # setor da empresa

    # Interesse no plano
    plan_type: PlanType = PlanType.UNKNOWN
    num_beneficiaries: Optional[int] = None    # vidas a contratar
    current_plan: Optional[str] = None         # plano atual, se houver
    current_operator: Optional[str] = None     # operadora atual
    budget_range: Optional[str] = None         # faixa de orçamento mensal
    desired_coverage: Optional[str] = None     # cobertura desejada (nacional, regional, etc.)

    # Qualificação
    score: int = 0                             # 0-100
    qualification_notes: Optional[str] = None
    pain_points: list[str] = field(default_factory=list)
    decision_timeline: Optional[str] = None    # "imediato", "30 dias", "3 meses"
    is_decision_maker: Optional[bool] = None

    # Histórico de interações
    interactions: list[dict] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)

    def add_interaction(self, channel: str, message: str, direction: str = "inbound"):
        self.interactions.append({
            "timestamp": datetime.now().isoformat(),
            "channel": channel,
            "message": message,
            "direction": direction,
        })
        self.updated_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "channel": self.channel.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "phone": self.phone,
            "email": self.email,
            "whatsapp": self.whatsapp,
            "company_name": self.company_name,
            "company_size": self.company_size,
            "cnpj": self.cnpj,
            "segment": self.segment,
            "plan_type": self.plan_type.value,
            "num_beneficiaries": self.num_beneficiaries,
            "current_plan": self.current_plan,
            "current_operator": self.current_operator,
            "budget_range": self.budget_range,
            "desired_coverage": self.desired_coverage,
            "score": self.score,
            "qualification_notes": self.qualification_notes,
            "pain_points": self.pain_points,
            "decision_timeline": self.decision_timeline,
            "is_decision_maker": self.is_decision_maker,
            "interactions": self.interactions,
            "raw_data": self.raw_data,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Lead":
        lead = cls(
            id=data["id"],
            name=data["name"],
            channel=LeadChannel(data["channel"]),
            status=LeadStatus(data.get("status", LeadStatus.NEW)),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        lead.phone = data.get("phone")
        lead.email = data.get("email")
        lead.whatsapp = data.get("whatsapp")
        lead.company_name = data.get("company_name")
        lead.company_size = data.get("company_size")
        lead.cnpj = data.get("cnpj")
        lead.segment = data.get("segment")
        lead.plan_type = PlanType(data.get("plan_type", PlanType.UNKNOWN))
        lead.num_beneficiaries = data.get("num_beneficiaries")
        lead.current_plan = data.get("current_plan")
        lead.current_operator = data.get("current_operator")
        lead.budget_range = data.get("budget_range")
        lead.desired_coverage = data.get("desired_coverage")
        lead.score = data.get("score", 0)
        lead.qualification_notes = data.get("qualification_notes")
        lead.pain_points = data.get("pain_points", [])
        lead.decision_timeline = data.get("decision_timeline")
        lead.is_decision_maker = data.get("is_decision_maker")
        lead.interactions = data.get("interactions", [])
        lead.raw_data = data.get("raw_data", {})
        return lead
