"""
Orquestrador Principal - DTS Lead Agent

Coordena o fluxo completo de captação e qualificação de leads:
  Canal → Descoberta → Qualificação → Notificação ao corretor

Usa o padrão de agentes da Anthropic SDK para orquestrar
os subagentes de descoberta e qualificação.
"""

import json
from dataclasses import dataclass
from typing import Optional

import anthropic

from src.agents.lead_discovery import LeadDiscoveryAgent
from src.agents.lead_qualifier import LeadQualifierAgent
from src.models.lead import LeadStatus
from src.storage.lead_repository import LeadRepository


ORCHESTRATOR_SYSTEM_PROMPT = """Você é o orquestrador do sistema de leads da DTS (corretora de planos de saúde).

Você coordena dois subagentes:
1. **Agente de Descoberta**: captura e registra novos leads de qualquer canal
2. **Agente de Qualificação**: avalia e pontua leads usando critérios BANT

Seu papel é:
- Entender a solicitação do usuário (corretor/gestor da DTS)
- Acionar o agente correto para a tarefa
- Apresentar resultados de forma clara e acionável
- Priorizar leads qualificados para o corretor

Métricas que você monitora:
- Taxa de conversão por canal
- Tempo médio de qualificação
- Leads qualificados aguardando atendimento

Responda sempre em português brasileiro, de forma profissional e objetiva."""


@dataclass
class OrchestratorResult:
    action: str
    lead_id: Optional[str]
    summary: str
    next_steps: list[str]
    data: dict


class LeadOrchestrator:
    def __init__(self, storage_path: str = "data/leads.json", model: str = "claude-sonnet-4-6"):
        self.repository = LeadRepository(storage_path)
        self.discovery_agent = LeadDiscoveryAgent(self.repository, model)
        self.qualifier_agent = LeadQualifierAgent(self.repository, model)
        self.client = anthropic.Anthropic()
        self.model = model

    # ── Canal: entrada de novo lead ──────────────────────────────────────────

    def ingest_lead(self, raw_input: str, channel: str = "manual") -> OrchestratorResult:
        """
        Fluxo completo para um novo lead:
        1. Descoberta e registro
        2. Qualificação imediata
        3. Retorna resultado consolidado
        """
        # 1. Descoberta
        discovery_result = self.discovery_agent.process_new_contact(raw_input, channel)

        # Pega o lead mais recente criado
        all_leads = self.repository.list_all()
        if not all_leads:
            return OrchestratorResult(
                action="ingest_failed",
                lead_id=None,
                summary="Não foi possível criar o lead.",
                next_steps=["Verifique os dados e tente novamente"],
                data=discovery_result,
            )

        # Lead mais recente
        latest_lead = sorted(all_leads, key=lambda l: l.created_at, reverse=True)[0]
        lead_id = latest_lead.id

        # 2. Qualificação
        qual_result = self.qualifier_agent.qualify_lead(lead_id)

        # 3. Determina próximas ações
        lead = self.repository.get(lead_id)
        next_steps = self._get_next_steps(lead)

        return OrchestratorResult(
            action="lead_ingested_and_qualified",
            lead_id=lead_id,
            summary=(
                f"Lead '{lead.name}' registrado (canal: {lead.channel.value}) | "
                f"Score: {lead.score}/100 | Status: {lead.status.value}"
            ),
            next_steps=next_steps,
            data={"discovery": discovery_result, "qualification": qual_result},
        )

    def process_lead_response(self, lead_id: str, response: str, channel: str) -> OrchestratorResult:
        """Processa resposta de um lead e re-qualifica."""
        qual_result = self.qualifier_agent.process_response(lead_id, response, channel)
        lead = self.repository.get(lead_id)

        if not lead:
            return OrchestratorResult(
                action="error",
                lead_id=lead_id,
                summary="Lead não encontrado",
                next_steps=[],
                data={},
            )

        return OrchestratorResult(
            action="lead_response_processed",
            lead_id=lead_id,
            summary=(
                f"Resposta de '{lead.name}' processada | "
                f"Score atualizado: {lead.score}/100 | Status: {lead.status.value}"
            ),
            next_steps=self._get_next_steps(lead),
            data=qual_result,
        )

    def qualify_pending(self) -> list[OrchestratorResult]:
        """Qualifica todos os leads pendentes (status = novo)."""
        results = self.qualifier_agent.qualify_all_new()
        orchestrator_results = []

        for result in results:
            lead_id = result.get("lead_id")
            lead = self.repository.get(lead_id) if lead_id else None
            orchestrator_results.append(
                OrchestratorResult(
                    action="batch_qualification",
                    lead_id=lead_id,
                    summary=result.get("summary", ""),
                    next_steps=self._get_next_steps(lead) if lead else [],
                    data=result,
                )
            )

        return orchestrator_results

    def get_qualified_leads(self) -> list[dict]:
        """Retorna leads qualificados aguardando atendimento do corretor."""
        leads = self.repository.list_by_status(LeadStatus.QUALIFIED)
        return [
            {
                "id": l.id,
                "name": l.name,
                "score": l.score,
                "plan_type": l.plan_type.value,
                "channel": l.channel.value,
                "company_name": l.company_name,
                "num_beneficiaries": l.num_beneficiaries,
                "budget_range": l.budget_range,
                "decision_timeline": l.decision_timeline,
                "pain_points": l.pain_points,
                "contact": l.phone or l.whatsapp or l.email,
                "notes": l.qualification_notes,
            }
            for l in sorted(leads, key=lambda x: x.score, reverse=True)
        ]

    def get_dashboard(self) -> dict:
        """Retorna visão consolidada para o corretor/gestor."""
        stats = self.repository.get_stats()
        qualified = self.get_qualified_leads()
        qualifying = self.repository.list_by_status(LeadStatus.QUALIFYING)

        return {
            "stats": stats,
            "qualified_leads": qualified,
            "qualifying_count": len(qualifying),
            "top_channels": self._get_top_channels(stats),
        }

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_next_steps(self, lead) -> list[str]:
        if not lead:
            return []

        if lead.status == LeadStatus.QUALIFIED:
            contact = lead.phone or lead.whatsapp or lead.email or "sem contato registrado"
            return [
                f"Entrar em contato com {lead.name} ({contact})",
                "Apresentar proposta personalizada",
                "Agendar reunião de consultoria",
            ]

        if lead.status == LeadStatus.QUALIFYING:
            missing = []
            if not lead.budget_range:
                missing.append("orçamento disponível")
            if lead.is_decision_maker is None:
                missing.append("confirmação de autoridade decisória")
            if not lead.decision_timeline:
                missing.append("prazo para contratação")
            if not lead.num_beneficiaries:
                missing.append("número de beneficiários")

            actions = [f"Enviar mensagem de qualificação via {lead.channel.value}"]
            if missing:
                actions.append(f"Coletar: {', '.join(missing)}")
            return actions

        if lead.status == LeadStatus.DISQUALIFIED:
            return ["Arquivar lead", "Agendar follow-up em 6 meses para reativação"]

        return ["Processar lead"]

    def _get_top_channels(self, stats: dict) -> list[dict]:
        channels = stats.get("by_channel", {})
        return sorted(
            [{"channel": ch, "count": ct} for ch, ct in channels.items()],
            key=lambda x: x["count"],
            reverse=True,
        )
