"""
Orquestrador Principal — DTS Lead Agent
Nicho: executivos ex-CLT que abriram PJ, precisam de plano para si + família (3+ vidas).
"""

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from src.agents.lead_discovery import LeadDiscoveryAgent
from src.agents.lead_qualifier import LeadQualifierAgent
from src.models.lead import Lead, LeadStatus, PortabilityStatus
from src.storage.lead_repository import LeadRepository


@dataclass
class OrchestratorResult:
    action: str
    lead_id: Optional[str]
    summary: str
    next_steps: list[str]
    alerts: list[str] = field(default_factory=list)   # alertas de urgência
    data: dict = field(default_factory=dict)


class LeadOrchestrator:
    def __init__(self, storage_path: str = "data/leads.json", model: str = "claude-sonnet-4-6"):
        self.repository = LeadRepository(storage_path)
        self.discovery_agent = LeadDiscoveryAgent(self.repository, model)
        self.qualifier_agent = LeadQualifierAgent(self.repository, model)

    # ── Fluxo principal ──────────────────────────────────────────────────────

    def ingest_lead(self, raw_input: str, channel: str = "manual") -> OrchestratorResult:
        """Descobre, registra e qualifica imediatamente um novo lead."""
        discovery_result = self.discovery_agent.process_new_contact(raw_input, channel)

        all_leads = self.repository.list_all()
        if not all_leads:
            return OrchestratorResult(
                action="ingest_failed",
                lead_id=None,
                summary="Não foi possível criar o lead.",
                next_steps=["Verifique os dados e tente novamente"],
            )

        lead = sorted(all_leads, key=lambda l: l.created_at, reverse=True)[0]
        lead_id = lead.id

        qual_result = self.qualifier_agent.qualify_lead(lead_id)

        lead = self.repository.get(lead_id)
        alerts = self._build_alerts(lead)
        next_steps = self._get_next_steps(lead)

        return OrchestratorResult(
            action="lead_ingested_and_qualified",
            lead_id=lead_id,
            summary=(
                f"Lead '{lead.name}' registrado | "
                f"Score: {lead.score}/100 | Status: {lead.status.value}"
            ),
            next_steps=next_steps,
            alerts=alerts,
            data={"discovery": discovery_result, "qualification": qual_result},
        )

    def process_lead_response(self, lead_id: str, response: str, channel: str) -> OrchestratorResult:
        """Processa resposta de um lead e re-qualifica."""
        qual_result = self.qualifier_agent.process_response(lead_id, response, channel)
        lead = self.repository.get(lead_id)

        if not lead:
            return OrchestratorResult(
                action="error", lead_id=lead_id,
                summary="Lead não encontrado", next_steps=[],
            )

        return OrchestratorResult(
            action="lead_response_processed",
            lead_id=lead_id,
            summary=(
                f"Resposta de '{lead.name}' processada | "
                f"Score: {lead.score}/100 | Status: {lead.status.value}"
            ),
            next_steps=self._get_next_steps(lead),
            alerts=self._build_alerts(lead),
            data=qual_result,
        )

    def qualify_pending(self) -> list[OrchestratorResult]:
        """Qualifica todos os leads com status 'novo'."""
        results = self.qualifier_agent.qualify_all_new()
        return [
            OrchestratorResult(
                action="batch_qualification",
                lead_id=r.get("lead_id"),
                summary=r.get("summary", ""),
                next_steps=self._get_next_steps(self.repository.get(r.get("lead_id"))),
                alerts=self._build_alerts(self.repository.get(r.get("lead_id"))),
                data=r,
            )
            for r in results
        ]

    # ── Consultas ────────────────────────────────────────────────────────────

    def get_qualified_leads(self) -> list[dict]:
        """Leads qualificados priorizados por score e urgência de portabilidade."""
        leads = self.repository.list_by_status(LeadStatus.QUALIFIED)

        def priority_key(l: Lead):
            portability_bonus = 20 if l.portability_status == PortabilityStatus.ELIGIBLE else 0
            children_bonus = 10 if l.has_children_under_12 else 0
            return l.score + portability_bonus + children_bonus

        leads.sort(key=priority_key, reverse=True)

        result = []
        for l in leads:
            days = l.days_since_leaving_company()
            portability_info = None
            if l.portability_status == PortabilityStatus.ELIGIBLE and days is not None:
                remaining = 60 - days
                portability_info = f"PORTABILIDADE: {remaining} dias restantes"

            result.append({
                "id": l.id,
                "name": l.name,
                "score": l.score,
                "score_breakdown": l.score_breakdown,
                "former_job_title": l.former_job_title,
                "former_company": l.former_company,
                "company_name": l.company_name,
                "family_composition": l.family_composition,
                "num_family_members": l.num_family_members,
                "previous_operator": l.previous_operator,
                "previous_plan_coverage": l.previous_plan_coverage,
                "budget_range": l.budget_range,
                "urgency_level": l.urgency_level,
                "portability_info": portability_info,
                "has_children_under_12": l.has_children_under_12,
                "contact": l.whatsapp or l.phone or l.email,
                "channel": l.channel.value,
                "notes": l.qualification_notes,
            })
        return result

    def get_dashboard(self) -> dict:
        stats = self.repository.get_stats()
        qualified = self.get_qualified_leads()
        qualifying = self.repository.list_by_status(LeadStatus.QUALIFYING)

        # Leads com portabilidade em prazo (alertas críticos)
        portability_alerts = [
            l for l in self.repository.list_all()
            if l.portability_status == PortabilityStatus.ELIGIBLE
            and l.status not in (LeadStatus.CONVERTED, LeadStatus.LOST)
        ]

        return {
            "stats": stats,
            "qualified_leads": qualified,
            "qualifying_count": len(qualifying),
            "portability_alerts": len(portability_alerts),
            "top_channels": self._get_top_channels(stats),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _build_alerts(self, lead: Optional[Lead]) -> list[str]:
        if not lead:
            return []
        alerts = []

        # Alerta de portabilidade
        if lead.portability_status == PortabilityStatus.ELIGIBLE:
            days = lead.days_since_leaving_company()
            if days is not None:
                remaining = 60 - days
                if remaining <= 15:
                    alerts.append(f"CRITICO: portabilidade vence em {remaining} dias!")
                else:
                    alerts.append(f"URGENTE: portabilidade disponivel por mais {remaining} dias")

        # Alerta de filhos pequenos sem plano
        if lead.has_children_under_12 and lead.status in (LeadStatus.NEW, LeadStatus.QUALIFYING):
            alerts.append("Filhos menores de 12 anos sem cobertura — urgência alta")

        # Alerta de mínimo de vidas
        if lead.num_family_members and lead.num_family_members < 3:
            alerts.append(
                f"Apenas {lead.num_family_members} vida(s) — mínimo do produto é 3. "
                "Verificar se há mais membros ou requalificar."
            )

        return alerts

    def _get_next_steps(self, lead: Optional[Lead]) -> list[str]:
        if not lead:
            return []

        if lead.status == LeadStatus.QUALIFIED:
            contact = lead.whatsapp or lead.phone or lead.email or "sem contato"
            steps = [f"Ligar / WhatsApp para {lead.name} ({contact})"]

            if lead.portability_status == PortabilityStatus.ELIGIBLE:
                days = lead.days_since_leaving_company()
                remaining = 60 - days if days else "?"
                steps.append(
                    f"Usar portabilidade como argumento de urgência ({remaining} dias restantes)"
                )

            if lead.previous_operator:
                steps.append(
                    f"Preparar comparativo com o plano anterior ({lead.previous_operator})"
                )

            steps.append("Enviar proposta PME Familiar com 3+ operadoras para comparação")

            if lead.has_children_under_12:
                steps.append("Destacar cobertura pediátrica e pronto-socorro na proposta")

            return steps

        if lead.status == LeadStatus.QUALIFYING:
            missing = []
            if not lead.num_family_members:
                missing.append("número de pessoas no plano (familiar)")
            if lead.had_corporate_plan is None:
                missing.append("se tinha plano pela empresa anterior")
            if not lead.left_company_date and lead.had_corporate_plan:
                missing.append("data de saída da empresa (para checar portabilidade)")
            if not lead.has_cnpj:
                missing.append("se já tem CNPJ aberto")

            steps = [f"Enviar mensagem de qualificação via {lead.channel.value}"]
            if missing:
                steps.append(f"Coletar: {', '.join(missing)}")
            return steps

        if lead.status == LeadStatus.DISQUALIFIED:
            reason = lead.raw_data.get("disqualification_reason", "critérios não atendidos")
            return [
                f"Arquivar: {reason}",
                "Nutrir com conteúdo sobre planos individuais (caso mude de contexto)",
            ]

        return ["Processar lead"]

    def _get_top_channels(self, stats: dict) -> list[dict]:
        channels = stats.get("by_channel", {})
        return sorted(
            [{"channel": ch, "count": ct} for ch, ct in channels.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
