"""
Agente de Descoberta de Leads (DTS)

Responsável por identificar e registrar leads a partir de diferentes canais.
Extrai informações iniciais e cria o registro no sistema.
"""

import json
from typing import Optional

import anthropic

from src.models.lead import Lead, LeadChannel, LeadStatus
from src.storage.lead_repository import LeadRepository
from src.tools.qualification_tools import DISCOVERY_TOOLS

SYSTEM_PROMPT = """Você é o agente de descoberta de leads da DTS, uma corretora especializada em planos de saúde.

Sua responsabilidade é:
1. Receber dados brutos de novos contatos (mensagens, formulários, indicações)
2. Extrair as informações relevantes disponíveis
3. Criar o registro do lead no sistema usando as ferramentas disponíveis
4. Classificar preliminarmente o tipo de plano de interesse

Contexto da DTS:
- Trabalhamos com planos de saúde individuais, familiares, PME (2-99 vidas) e empresariais (100+ vidas)
- Também oferecemos planos odontológicos
- Operamos com as principais operadoras: Unimed, Bradesco Saúde, SulAmérica, Amil, Porto Seguro Saúde, Hapvida

Ao processar um novo contato:
- Sempre crie o lead com as informações disponíveis
- Não invente informações que não foram fornecidas
- Se o canal for WhatsApp ou ligação, extraia o número de contato
- Identifique se é pessoa física (PF) ou jurídica (PJ) quando possível
- Seja objetivo e eficiente

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
            if tool_input.get("plan_type"):
                from src.models.lead import PlanType
                try:
                    lead.plan_type = PlanType(tool_input["plan_type"])
                except ValueError:
                    pass

            if tool_input.get("raw_message"):
                lead.raw_data["raw_message"] = tool_input["raw_message"]
                lead.add_interaction(channel.value, tool_input["raw_message"], "inbound")

            self.repository.update(lead)
            return json.dumps({"success": True, "lead_id": lead.id, "lead_name": lead.name})

        if tool_name == "listar_leads_novos":
            leads = self.repository.list_by_status(LeadStatus.NEW)
            return json.dumps([{"id": l.id, "name": l.name, "channel": l.channel.value} for l in leads])

        if tool_name == "obter_estatisticas":
            return json.dumps(self.repository.get_stats())

        return json.dumps({"error": f"Ferramenta '{tool_name}' não reconhecida"})

    def process_new_contact(self, raw_input: str, channel_hint: Optional[str] = None) -> dict:
        """
        Processa um novo contato bruto e cria o lead no sistema.

        Args:
            raw_input: Texto bruto com informações do contato (mensagem, formulário, etc.)
            channel_hint: Dica sobre o canal de origem (opcional)

        Returns:
            Dict com dados do lead criado
        """
        user_message = f"Novo contato recebido:\n\n{raw_input}"
        if channel_hint:
            user_message += f"\n\nCanal de origem: {channel_hint}"

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
                # Extrai texto da resposta
                text = next(
                    (block.text for block in response.content if hasattr(block, "text")),
                    "Lead processado com sucesso.",
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

        return {"status": "error", "message": "Resposta inesperada do agente"}

    def get_summary(self) -> str:
        """Retorna um resumo dos leads no sistema."""
        stats = self.repository.get_stats()
        lines = [
            "=== Resumo de Leads - DTS ===",
            f"Total: {stats['total']}",
            "\nPor status:",
        ]
        for status, count in stats.get("by_status", {}).items():
            lines.append(f"  {status}: {count}")
        lines.append("\nPor canal:")
        for channel, count in stats.get("by_channel", {}).items():
            lines.append(f"  {channel}: {count}")
        return "\n".join(lines)
