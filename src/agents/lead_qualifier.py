"""
Agente de Qualificação de Leads (DTS)

Responsável por qualificar leads usando a metodologia BANT adaptada para
o mercado de planos de saúde:
- Budget (Orçamento): qual é a faixa de investimento esperada?
- Authority (Autoridade): é o tomador de decisão?
- Need (Necessidade): qual a real necessidade/dor?
- Timeline (Prazo): quando pretende contratar?

Score >= 60 → Lead Qualificado
Score 30-59 → Qualificação em andamento
Score < 30  → Lead Desqualificado
"""

import json

import anthropic

from src.models.lead import Lead, LeadStatus, PlanType
from src.storage.lead_repository import LeadRepository
from src.tools.qualification_tools import QUALIFICATION_TOOLS

SYSTEM_PROMPT = """Você é o agente de qualificação de leads da DTS, uma corretora especializada em planos de saúde.

Sua responsabilidade é analisar os dados de um lead e qualificá-lo usando a metodologia BANT adaptada:

CRITÉRIOS DE PONTUAÇÃO (total = 100 pontos):

1. BUDGET - Orçamento (25 pts)
   - 25 pts: Orçamento definido e compatível com os planos DTS
   - 15 pts: Tem orçamento mas ainda indefinido
   - 5 pts: Sem informação de orçamento

2. AUTHORITY - Tomador de decisão (20 pts)
   - 20 pts: É o tomador de decisão final
   - 10 pts: Influenciador com acesso ao decisor
   - 0 pts: Sem acesso ao decisor / desconhecido

3. NEED - Necessidade clara (30 pts)
   - 30 pts: Necessidade urgente e bem definida (dores claras, plano atual insatisfatório)
   - 20 pts: Necessidade moderada (quer melhorar mas sem urgência)
   - 10 pts: Interesse difuso (apenas pesquisando preços)
   - 0 pts: Sem necessidade clara

4. TIMELINE - Prazo (25 pts)
   - 25 pts: Decisão imediata ou até 30 dias
   - 15 pts: 30 a 90 dias
   - 5 pts: Mais de 90 dias
   - 0 pts: Sem prazo definido

CLASSIFICAÇÃO FINAL:
- 60-100: QUALIFICADO → Encaminhar para o corretor
- 30-59: EM QUALIFICAÇÃO → Continuar engajamento
- 0-29: DESQUALIFICADO → Arquivar ou nutrir a longo prazo

Contexto da DTS:
- Especialistas em planos PME (2-99 vidas) e empresariais (100+ vidas)
- Também atendemos pessoa física e familiar
- Parceiros: Unimed, Bradesco Saúde, SulAmérica, Amil, Porto Seguro Saúde, Hapvida, NotreDame
- Diferenciais: atendimento personalizado, comparativo de operadoras, assessoria completa

Ao qualificar:
1. Primeiro busque os dados do lead
2. Analise criteriosamente cada dimensão BANT
3. Identifique as informações faltantes mais críticas
4. Calcule o score e determine o status
5. Se faltar informação crítica, gere uma mensagem de qualificação personalizada

Responda sempre em português brasileiro."""


class LeadQualifierAgent:
    def __init__(self, repository: LeadRepository, model: str = "claude-sonnet-4-6"):
        self.repository = repository
        self.client = anthropic.Anthropic()
        self.model = model

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "buscar_lead":
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            return json.dumps(lead.to_dict())

        if tool_name == "atualizar_lead":
            lead_id = tool_input.pop("lead_id")
            lead = self.repository.get(lead_id)
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})

            if "plan_type" in tool_input:
                try:
                    lead.plan_type = PlanType(tool_input["plan_type"])
                except ValueError:
                    pass

            for field in ["num_beneficiaries", "company_size", "budget_range",
                          "current_operator", "decision_timeline", "is_decision_maker",
                          "desired_coverage", "pain_points"]:
                if field in tool_input:
                    setattr(lead, field, tool_input[field])

            self.repository.update(lead)
            return json.dumps({"success": True, "lead_id": lead.id})

        if tool_name == "calcular_score":
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})

            lead.score = tool_input["score"]
            lead.qualification_notes = tool_input["justification"]

            status_map = {
                "qualificado": LeadStatus.QUALIFIED,
                "desqualificado": LeadStatus.DISQUALIFIED,
                "qualificando": LeadStatus.QUALIFYING,
            }
            lead.status = status_map.get(tool_input["status"], LeadStatus.QUALIFYING)
            self.repository.update(lead)
            return json.dumps({"success": True, "score": lead.score, "status": lead.status.value})

        if tool_name == "registrar_interacao":
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})

            lead.add_interaction(
                tool_input["channel"],
                tool_input["message"],
                tool_input.get("direction", "outbound"),
            )
            self.repository.update(lead)
            return json.dumps({"success": True})

        if tool_name == "gerar_mensagem_qualificacao":
            # O agente irá gerar a mensagem via LLM - retornamos template base
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            return json.dumps({
                "lead_name": lead.name,
                "channel": tool_input["channel"],
                "missing_info": tool_input["missing_info"],
                "instruction": "Gere uma mensagem natural e personalizada para coletar essas informações",
            })

        return json.dumps({"error": f"Ferramenta '{tool_name}' não reconhecida"})

    def qualify_lead(self, lead_id: str) -> dict:
        """
        Qualifica um lead existente pelo seu ID.

        Returns:
            Dict com score, status e mensagem de qualificação (se necessário)
        """
        messages = [{"role": "user", "content": f"Por favor, qualifique o lead com ID: {lead_id}"}]

        result = {"lead_id": lead_id, "score": None, "status": None, "qualification_message": None}

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=QUALIFICATION_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "",
                )
                result["summary"] = text

                # Atualiza com dados mais recentes do repositório
                lead = self.repository.get(lead_id)
                if lead:
                    result["score"] = lead.score
                    result["status"] = lead.status.value
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = self._handle_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result,
                        })

                        # Captura mensagem de qualificação gerada
                        if block.name == "gerar_mensagem_qualificacao":
                            result["_pending_message_context"] = json.loads(tool_result)

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return result

    def qualify_all_new(self) -> list[dict]:
        """Qualifica todos os leads com status 'novo'."""
        new_leads = self.repository.list_by_status(LeadStatus.NEW)
        results = []
        for lead in new_leads:
            lead.status = LeadStatus.QUALIFYING
            self.repository.update(lead)
            result = self.qualify_lead(lead.id)
            results.append(result)
        return results

    def process_response(self, lead_id: str, response_text: str, channel: str) -> dict:
        """
        Processa a resposta de um lead a uma mensagem de qualificação.

        Args:
            lead_id: ID do lead
            response_text: Texto da resposta do lead
            channel: Canal onde a resposta foi recebida

        Returns:
            Dict com novo score e próxima ação recomendada
        """
        lead = self.repository.get(lead_id)
        if not lead:
            return {"error": "Lead não encontrado"}

        lead.add_interaction(channel, response_text, "inbound")
        self.repository.update(lead)

        messages = [
            {
                "role": "user",
                "content": (
                    f"O lead {lead_id} respondeu à nossa mensagem de qualificação.\n\n"
                    f"Resposta recebida via {channel}:\n\"{response_text}\"\n\n"
                    "Por favor:\n"
                    "1. Atualize os dados do lead com as informações da resposta\n"
                    "2. Recalcule o score de qualificação\n"
                    "3. Determine se o lead está qualificado ou se precisamos de mais informações"
                ),
            }
        ]

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=QUALIFICATION_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "",
                )
                lead = self.repository.get(lead_id)
                return {
                    "lead_id": lead_id,
                    "score": lead.score if lead else None,
                    "status": lead.status.value if lead else None,
                    "summary": text,
                }

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_result = self._handle_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": tool_result,
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

        return {"error": "Resposta inesperada"}
