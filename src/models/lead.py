from dataclasses import dataclass, field
from datetime import datetime, date
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
    PME_FAMILY = "pme_familiar"   # Nicho principal: executivo PJ + família
    PME = "pme"
    INDIVIDUAL = "individual"
    FAMILY = "familiar"
    CORPORATE = "empresarial"
    DENTAL = "odontologico"
    UNKNOWN = "desconhecido"


class PortabilityStatus(str, Enum):
    ELIGIBLE = "elegivel"           # Dentro do prazo de 60 dias
    EXPIRED = "expirado"            # Perdeu o prazo de portabilidade
    NOT_APPLICABLE = "nao_aplica"   # Nunca teve plano corporativo
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

    # Perfil executivo PJ — campos centrais do nicho
    former_company: Optional[str] = None         # Empresa de onde saiu
    former_job_title: Optional[str] = None       # Cargo que ocupava
    left_company_date: Optional[str] = None      # Data de saída (AAAA-MM ou AAAA-MM-DD)
    has_cnpj: Optional[bool] = None              # Já abriu o CNPJ?
    company_name: Optional[str] = None           # Nome da empresa PJ aberta
    cnpj: Optional[str] = None

    # Família — regra de negócio: mínimo 3 vidas para PME familiar
    num_family_members: Optional[int] = None     # Total incluindo o titular
    family_composition: Optional[str] = None     # Ex: "titular + cônjuge + 2 filhos"
    children_ages: Optional[str] = None          # Idades dos filhos (relevante para carência)

    # Plano anterior (portabilidade)
    had_corporate_plan: Optional[bool] = None    # Tinha plano pela empresa anterior?
    previous_operator: Optional[str] = None      # Operadora do plano anterior
    previous_plan_name: Optional[str] = None     # Nome/tipo do plano anterior
    previous_plan_coverage: Optional[str] = None # Nacional / regional / enfermaria / apartamento
    portability_status: PortabilityStatus = PortabilityStatus.UNKNOWN
    portability_deadline: Optional[str] = None   # Data limite para usar portabilidade

    # Interesse no novo plano
    plan_type: PlanType = PlanType.UNKNOWN
    num_beneficiaries: Optional[int] = None      # vidas totais no plano
    desired_coverage: Optional[str] = None       # nacional, estadual, etc.
    desired_accommodation: Optional[str] = None  # apartamento, enfermaria
    budget_range: Optional[str] = None           # faixa de orçamento total/mês
    wants_dental: Optional[bool] = None          # interesse em odonto junto

    # Motivação e urgência
    reason_for_leaving: Optional[str] = None     # contexto da saída (demissão, pedido)
    urgency_level: Optional[str] = None          # "imediata", "até 30 dias", "sem urgência"
    # Dica de ouro: se perdeu plano e tem filhos pequenos, urgência é máxima
    has_children_under_12: Optional[bool] = None

    # Financeiro PJ — diferencial do nicho
    can_deduct_as_pj_expense: Optional[bool] = None  # Sabe que pode deduzir como despesa PJ?
    annual_revenue_estimate: Optional[str] = None    # Faixa de faturamento PJ

    # Qualificação BANT adaptada
    score: int = 0
    score_breakdown: dict = field(default_factory=dict)  # detalhamento por dimensão
    qualification_notes: Optional[str] = None
    pain_points: list[str] = field(default_factory=list)
    decision_timeline: Optional[str] = None
    is_decision_maker: Optional[bool] = None    # Para PJ próprio, sempre True

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

    def days_since_leaving_company(self) -> Optional[int]:
        if not self.left_company_date:
            return None
        try:
            left = datetime.strptime(self.left_company_date[:10], "%Y-%m-%d").date()
            return (date.today() - left).days
        except ValueError:
            return None

    def is_within_portability_window(self) -> Optional[bool]:
        days = self.days_since_leaving_company()
        if days is None:
            return None
        return days <= 60  # ANS: 60 dias após demissão

    def is_minimum_viable(self) -> bool:
        """Regra mínima do nicho: 3+ vidas no plano."""
        members = self.num_family_members or self.num_beneficiaries
        return members is not None and members >= 3

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
            "former_company": self.former_company,
            "former_job_title": self.former_job_title,
            "left_company_date": self.left_company_date,
            "has_cnpj": self.has_cnpj,
            "company_name": self.company_name,
            "cnpj": self.cnpj,
            "num_family_members": self.num_family_members,
            "family_composition": self.family_composition,
            "children_ages": self.children_ages,
            "had_corporate_plan": self.had_corporate_plan,
            "previous_operator": self.previous_operator,
            "previous_plan_name": self.previous_plan_name,
            "previous_plan_coverage": self.previous_plan_coverage,
            "portability_status": self.portability_status.value,
            "portability_deadline": self.portability_deadline,
            "plan_type": self.plan_type.value,
            "num_beneficiaries": self.num_beneficiaries,
            "desired_coverage": self.desired_coverage,
            "desired_accommodation": self.desired_accommodation,
            "budget_range": self.budget_range,
            "wants_dental": self.wants_dental,
            "reason_for_leaving": self.reason_for_leaving,
            "urgency_level": self.urgency_level,
            "has_children_under_12": self.has_children_under_12,
            "can_deduct_as_pj_expense": self.can_deduct_as_pj_expense,
            "annual_revenue_estimate": self.annual_revenue_estimate,
            "score": self.score,
            "score_breakdown": self.score_breakdown,
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
            status=LeadStatus(data.get("status", LeadStatus.NEW.value)),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
        lead.phone = data.get("phone")
        lead.email = data.get("email")
        lead.whatsapp = data.get("whatsapp")
        lead.former_company = data.get("former_company")
        lead.former_job_title = data.get("former_job_title")
        lead.left_company_date = data.get("left_company_date")
        lead.has_cnpj = data.get("has_cnpj")
        lead.company_name = data.get("company_name")
        lead.cnpj = data.get("cnpj")
        lead.num_family_members = data.get("num_family_members")
        lead.family_composition = data.get("family_composition")
        lead.children_ages = data.get("children_ages")
        lead.had_corporate_plan = data.get("had_corporate_plan")
        lead.previous_operator = data.get("previous_operator")
        lead.previous_plan_name = data.get("previous_plan_name")
        lead.previous_plan_coverage = data.get("previous_plan_coverage")
        lead.portability_status = PortabilityStatus(
            data.get("portability_status", PortabilityStatus.UNKNOWN.value)
        )
        lead.portability_deadline = data.get("portability_deadline")
        lead.plan_type = PlanType(data.get("plan_type", PlanType.UNKNOWN.value))
        lead.num_beneficiaries = data.get("num_beneficiaries")
        lead.desired_coverage = data.get("desired_coverage")
        lead.desired_accommodation = data.get("desired_accommodation")
        lead.budget_range = data.get("budget_range")
        lead.wants_dental = data.get("wants_dental")
        lead.reason_for_leaving = data.get("reason_for_leaving")
        lead.urgency_level = data.get("urgency_level")
        lead.has_children_under_12 = data.get("has_children_under_12")
        lead.can_deduct_as_pj_expense = data.get("can_deduct_as_pj_expense")
        lead.annual_revenue_estimate = data.get("annual_revenue_estimate")
        lead.score = data.get("score", 0)
        lead.score_breakdown = data.get("score_breakdown", {})
        lead.qualification_notes = data.get("qualification_notes")
        lead.pain_points = data.get("pain_points", [])
        lead.decision_timeline = data.get("decision_timeline")
        lead.is_decision_maker = data.get("is_decision_maker")
        lead.interactions = data.get("interactions", [])
        lead.raw_data = data.get("raw_data", {})
        return lead
