"""
Agente de Descoberta de Leads — DTS
Nicho: executivos ex-CLT que abriram PJ, precisam de plano para si + família (3+ vidas).
"""

import json
from typing import Optional

import anthropic

from src.models.lead import Lead, LeadChannel, LeadStatus, PlanType
from src.storage.lead_repository import LeadRepository
from src.tools.qualification_tools import DISCOVERY_TOOLS

SYSTEM_PROMPT = """Você é o agente de descoberta de leads da DTS, corretora especializada em planos de saúde para executivos que abriram sua própria empresa (PJ).

PERFIL DO LEAD IDEAL:
- Executivo (gerente, diretor, C-level, sócio) que saiu de uma empresa CLT
- Abriu ou está abrindo seu próprio CNPJ
- Precisa de plano de saúde para si + família (mínimo 3 pessoas: titular + cônjuge + filhos)
- Perdeu o plano corporativo da empresa anterior
- Busca manter o padrão de cobertura que tinha (nacional, apartamento)

SINAIS DE ALERTA POSITIVOS (lead quente):
- Menciona que "saiu da empresa", "abriu minha empresa", "me tornei PJ", "virei sócio"
- Menciona cônjuge e/ou filhos precisando de cobertura
- Faz referência ao plano que tinha antes (Bradesco, SulAmérica, Unimed, Amil, etc.)
- Menciona urgência: "preciso logo", "estou sem plano", "minha filha precisa de pediatra"
- Cargo anterior de nível gerencial ou superior

SINAIS DE ATENÇÃO (pode não se encaixar no nicho):
- Apenas 1-2 pessoas (mínimo do produto é 3 vidas via PME)
- Continua CLT (não é PJ ainda)
- Menos de 2 anos de carreira profissional

AO PROCESSAR UM CONTATO:
1. Identifique nome, contato e canal
2. Extraia cargo e empresa anterior, se mencionados
3. Identifique se mencionou família / número de pessoas
4. Verifique se houve menção a plano anterior e qual operadora
5. Capture a data de saída da empresa se mencionada
6. Crie o lead com todas as informações disponíveis

NÃO invente informações. Crie o lead com o que houver disponível.
Responda sempre em português brasileiro."""


class LeadDiscoveryAgent:
    def __init__(self, repository: LeadRepository, model: str = "claude-sonnet-4-6"):
        self.repository = repository
        self.client = anthropic.Anthropic()
        self.model = model

    def _handle_tool_call(self, tool_name: str, tool_input: dict) -> str:
        if tool_name == "criar_lead":
            channel = LeadChannel(tool_input["channel"])
            lead = self.repository.create(
                name=tool_input["name"],
                channel=channel,
                phone=tool_input.get("phone"),
                email=tool_input.get("email"),
                whatsapp=tool_input.get("whatsapp"),
                company_name=tool_input.get("company_name"),
            )

            # Campos específicos do nicho executivo PJ
            for field in [
                "former_company", "former_job_title", "left_company_date",
                "has_cnpj", "num_family_members", "had_corporate_plan",
                "previous_operator",
            ]:
                if tool_input.get(field) is not None:
                    setattr(lead, field, tool_input[field])

            # Sincroniza beneficiários com membros da família
            if lead.num_family_members:
                lead.num_beneficiaries = lead.num_family_members

            # Define tipo de plano padrão do nicho
            if lead.num_family_members and lead.num_family_members >= 3:
                lead.plan_type = PlanType.PME_FAMILY

            if tool_input.get("raw_message"):
                lead.raw_data["raw_message"] = tool_input["raw_message"]
                lead.add_interaction(channel.value, tool_input["raw_message"], "inbound")

            self.repository.update(lead)

            return json.dumps({
                "success": True,
                "lead_id": lead.id,
                "lead_name": lead.name,
                "num_family_members": lead.num_family_members,
                "is_minimum_viable": lead.is_minimum_viable(),
                "alert": (
                    "ATENÇÃO: menos de 3 vidas informadas. Verificar se é o nicho correto."
                    if lead.num_family_members and lead.num_family_members < 3
                    else None
                ),
            })

        if tool_name == "listar_leads_novos":
            leads = self.repository.list_by_status(LeadStatus.NEW)
            return json.dumps([
                {
                    "id": l.id,
                    "name": l.name,
                    "channel": l.channel.value,
                    "num_family_members": l.num_family_members,
                    "former_job_title": l.former_job_title,
                }
                for l in leads
            ])

        if tool_name == "obter_estatisticas":
            return json.dumps(self.repository.get_stats())

        return json.dumps({"error": f"Ferramenta '{tool_name}' não reconhecida"})

    def process_new_contact(self, raw_input: str, channel_hint: Optional[str] = None) -> dict:
        user_message = f"Novo contato recebido:\n\n{raw_input}"
        if channel_hint:
            user_message += f"\n\nCanal: {channel_hint}"

        messages = [{"role": "user", "content": user_message}]

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=DISCOVERY_TOOLS,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                text = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "Lead processado.",
                )
                return {"status": "success", "message": text}

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
                break

        return {"status": "error", "message": "Resposta inesperada"}

    def get_summary(self) -> str:
        stats = self.repository.get_stats()
        lines = [
            "=== Leads DTS — Executivos PJ ===",
            f"Total: {stats['total']}",
            "\nPor status:",
        ]
        for status, count in stats.get("by_status", {}).items():
            lines.append(f"  {status}: {count}")
        lines.append("\nPor canal:")
        for channel, count in stats.get("by_channel", {}).items():
            lines.append(f"  {channel}: {count}")
        return "\n".join(lines)
