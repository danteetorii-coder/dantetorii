"""
Agente de Qualificação de Leads — DTS
Nicho: executivos ex-CLT que abriram PJ, precisam de plano para si + família (3+ vidas).

Metodologia BANT adaptada ao nicho:

  Budget    (25 pts) — capacidade financeira; executivo PJ pode deduzir como despesa
  Authority (20 pts) — dono da PJ é sempre decisor, mas confirmar se cônjuge influencia
  Need      (30 pts) — 3+ vidas, filhos pequenos, sem plano no momento, perdeu cobertura
  Timeline  (25 pts) — portabilidade (60 dias ANS), filhos sem pediatra, urgência declarada

Score >= 60 → Qualificado (encaminhar para cotação imediata)
Score 30-59 → Em qualificação (coletar informações faltantes)
Score  < 30 → Desqualificado (menos de 3 vidas, sem PJ, sem interesse real)

REGRA DURA: menos de 3 vidas no plano = desqualificado para este nicho.
"""

import json

import anthropic

from src.models.lead import Lead, LeadStatus, PlanType, PortabilityStatus
from src.storage.lead_repository import LeadRepository
from src.tools.qualification_tools import QUALIFICATION_TOOLS

SYSTEM_PROMPT = """Você é o agente de qualificação de leads da DTS, corretora especializada em planos de saúde para executivos que abriram sua própria empresa (PJ).

NICHO-ALVO:
Executivos que saíram de empresas (CLT) e abriram CNPJ. Precisam de plano de saúde para si próprios e família — sempre com 3 ou mais vidas. Estão acostumados com planos corporativos premium e não querem perder qualidade.

DOR CENTRAL:
Perderam o plano de saúde da empresa ao sair. Muitos têm filhos pequenos e cônjuge sem cobertura. Estão correndo contra o prazo de portabilidade de carências da ANS (60 dias após a demissão/saída).

CRITÉRIOS DE PONTUAÇÃO BANT — total 100 pontos:

1. BUDGET — Capacidade financeira (25 pts)
   25 pts: Orçamento definido OU faturamento PJ alto OU sabe que pode deduzir como despesa
   15 pts: Tem condições mas orçamento indefinido
   5 pts:  Sem informação financeira

2. AUTHORITY — Tomador de decisão (20 pts)
   20 pts: Dono da PJ confirmado (decisor único)
   10 pts: Decisor, mas cônjuge também influencia (pedir para incluir cônjuge na conversa)
   0 pts:  Não é o dono / sem informação

3. NEED — Necessidade real (30 pts)
   30 pts: 3+ vidas + sem plano atual + filhos pequenos
   22 pts: 3+ vidas + sem plano atual (sem filhos)
   15 pts: 3+ vidas + plano atual precário (quer melhorar)
   5 pts:  2 vidas ou menos (FORA DO NICHO)
   0 pts:  Menos de 2 vidas / não precisa

4. TIMELINE — Urgência (25 pts)
   25 pts: Portabilidade elegível (dentro dos 60 dias) OU filhos sem pediatra agora
   15 pts: Quer contratar em até 30 dias sem portabilidade
   8 pts:  30 a 90 dias
   0 pts:  Sem prazo / só pesquisando

ALERTAS AUTOMÁTICOS:
- Se num_family_members < 3: DESQUALIFICAR com mensagem explicando que o produto mínimo é PME com 3 vidas
- Se portabilidade elegível: SEMPRE mencionar o prazo de 60 dias como urgência
- Se has_children_under_12: aumentar urgência (pediatra, vacinas, emergências)

ARGUMENTOS DE VENDA PARA USAR NAS MENSAGENS:
- "Como PJ, o plano entra como despesa da empresa, reduzindo o imposto"
- "Com a portabilidade, você aproveita as carências que já cumpriu no plano anterior"
- "Executivos que migraram para PME familiar mantêm a mesma qualidade de cobertura"
- "Trabalhamos com Bradesco Saúde, SulAmérica, Amil, Porto Seguro — mesmo padrão corporativo"

PERGUNTAS-CHAVE para coletar se faltarem:
1. "Quantas pessoas entrariam no plano?" (titular + família)
2. "Quando você saiu da empresa?" (para checar portabilidade)
3. "Você tinha plano de saúde pela empresa? Qual operadora?" (para portabilidade)
4. "Já tem o CNPJ aberto?" (necessário para contrato PME)
5. "Qual era o padrão do seu plano anterior?" (nacional? apartamento?)

Responda sempre em português brasileiro. Seja consultivo, não invasivo."""


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
            data = lead.to_dict()
            # Adiciona contexto calculado automaticamente
            data["days_since_leaving"] = lead.days_since_leaving_company()
            data["within_portability_window"] = lead.is_within_portability_window()
            data["is_minimum_viable"] = lead.is_minimum_viable()
            return json.dumps(data)

        if tool_name == "atualizar_perfil_executivo":
            lead_id = tool_input.pop("lead_id")
            lead = self.repository.get(lead_id)
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            for field in [
                "former_company", "former_job_title", "left_company_date", "has_cnpj",
                "company_name", "cnpj", "had_corporate_plan", "previous_operator",
                "previous_plan_coverage", "previous_plan_name", "reason_for_leaving",
                "annual_revenue_estimate",
            ]:
                if field in tool_input:
                    setattr(lead, field, tool_input[field])
            self.repository.update(lead)
            return json.dumps({"success": True, "lead_id": lead.id})

        if tool_name == "atualizar_familia":
            lead_id = tool_input.pop("lead_id")
            lead = self.repository.get(lead_id)
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            for field in [
                "num_family_members", "family_composition", "children_ages",
                "has_children_under_12", "wants_dental",
            ]:
                if field in tool_input:
                    setattr(lead, field, tool_input[field])
            # Sincroniza num_beneficiaries com num_family_members
            if lead.num_family_members:
                lead.num_beneficiaries = lead.num_family_members
            self.repository.update(lead)
            return json.dumps({
                "success": True,
                "is_minimum_viable": lead.is_minimum_viable(),
                "num_family_members": lead.num_family_members,
            })

        if tool_name == "atualizar_interesse_plano":
            lead_id = tool_input.pop("lead_id")
            lead = self.repository.get(lead_id)
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            for field in [
                "desired_coverage", "desired_accommodation", "budget_range",
                "urgency_level", "can_deduct_as_pj_expense",
            ]:
                if field in tool_input:
                    setattr(lead, field, tool_input[field])
            self.repository.update(lead)
            return json.dumps({"success": True})

        if tool_name == "avaliar_portabilidade":
            lead_id = tool_input.pop("lead_id")
            lead = self.repository.get(lead_id)
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            lead.portability_status = PortabilityStatus(tool_input["portability_status"])
            if "portability_deadline" in tool_input:
                lead.portability_deadline = tool_input["portability_deadline"]
            self.repository.update(lead)
            days_remaining = tool_input.get("days_remaining")
            return json.dumps({
                "success": True,
                "portability_status": lead.portability_status.value,
                "days_remaining": days_remaining,
                "urgency_message": (
                    f"ATENÇÃO: portabilidade elegível! Restam {days_remaining} dias."
                    if lead.portability_status == PortabilityStatus.ELIGIBLE and days_remaining
                    else None
                ),
            })

        if tool_name == "calcular_score":
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            lead.score = tool_input["score"]
            lead.score_breakdown = tool_input.get("score_breakdown", {})
            lead.qualification_notes = tool_input["justification"]
            if tool_input.get("disqualification_reason"):
                lead.raw_data["disqualification_reason"] = tool_input["disqualification_reason"]
            status_map = {
                "qualificado": LeadStatus.QUALIFIED,
                "desqualificado": LeadStatus.DISQUALIFIED,
                "qualificando": LeadStatus.QUALIFYING,
            }
            lead.status = status_map.get(tool_input["status"], LeadStatus.QUALIFYING)
            # PME familiar é o tipo padrão do nicho
            if lead.status == LeadStatus.QUALIFIED and lead.plan_type == PlanType.UNKNOWN:
                lead.plan_type = PlanType.PME_FAMILY
            self.repository.update(lead)
            return json.dumps({
                "success": True,
                "score": lead.score,
                "status": lead.status.value,
                "breakdown": lead.score_breakdown,
            })

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
            lead = self.repository.get(tool_input["lead_id"])
            if not lead:
                return json.dumps({"error": "Lead não encontrado"})
            return json.dumps({
                "lead_name": lead.name,
                "channel": tool_input["channel"],
                "missing_info": tool_input["missing_info"],
                "highlight_portability": tool_input.get("highlight_portability", False),
                "days_since_leaving": lead.days_since_leaving_company(),
                "within_portability_window": lead.is_within_portability_window(),
            })

        return json.dumps({"error": f"Ferramenta '{tool_name}' não reconhecida"})

    def _run_agent_loop(self, messages: list) -> tuple[str, list]:
        """Executa o loop de tool use do agente. Retorna (texto final, mensagens)."""
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
                return text, messages

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._handle_tool_call(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                return "", messages

    def qualify_lead(self, lead_id: str) -> dict:
        messages = [{"role": "user", "content": (
            f"Qualifique o lead ID: {lead_id}\n\n"
            "Passos:\n"
            "1. Busque os dados do lead\n"
            "2. Verifique se tem 3+ vidas (regra mínima do nicho)\n"
            "3. Avalie a portabilidade se houver data de saída da empresa\n"
            "4. Calcule o score BANT com breakdown por dimensão\n"
            "5. Se faltar informação crítica, indique quais perguntas fazer"
        )}]

        text, _ = self._run_agent_loop(messages)
        lead = self.repository.get(lead_id)
        return {
            "lead_id": lead_id,
            "score": lead.score if lead else None,
            "status": lead.status.value if lead else None,
            "portability_status": lead.portability_status.value if lead else None,
            "is_minimum_viable": lead.is_minimum_viable() if lead else None,
            "summary": text,
        }

    def qualify_all_new(self) -> list[dict]:
        new_leads = self.repository.list_by_status(LeadStatus.NEW)
        results = []
        for lead in new_leads:
            lead.status = LeadStatus.QUALIFYING
            self.repository.update(lead)
            results.append(self.qualify_lead(lead.id))
        return results

    def process_response(self, lead_id: str, response_text: str, channel: str) -> dict:
        lead = self.repository.get(lead_id)
        if not lead:
            return {"error": "Lead não encontrado"}

        lead.add_interaction(channel, response_text, "inbound")
        self.repository.update(lead)

        messages = [{"role": "user", "content": (
            f"O lead {lead_id} respondeu via {channel}:\n\n\"{response_text}\"\n\n"
            "Por favor:\n"
            "1. Extraia e atualize todas as informações relevantes da resposta\n"
            "2. Verifique se agora temos as 3+ vidas necessárias\n"
            "3. Reavalie a portabilidade com base em qualquer data mencionada\n"
            "4. Recalcule o score BANT\n"
            "5. Se ainda faltar informação crítica, gere mensagem de qualificação"
        )}]

        text, _ = self._run_agent_loop(messages)
        lead = self.repository.get(lead_id)
        return {
            "lead_id": lead_id,
            "score": lead.score if lead else None,
            "status": lead.status.value if lead else None,
            "portability_status": lead.portability_status.value if lead else None,
            "summary": text,
        }
