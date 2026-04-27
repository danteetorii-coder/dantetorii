"""
DTS Lead Agent - Ponto de entrada principal

Uso:
  python -m src.main ingest "Mensagem ou dados do lead"
  python -m src.main qualify-all
  python -m src.main dashboard
  python -m src.main qualified
  python -m src.main respond <lead_id> "Resposta do lead"
  python -m src.main demo
"""

import argparse
import json
import os
import sys

from src.agents.orchestrator import LeadOrchestrator
from src.channels.email_channel import EmailChannel
from src.channels.linkedin import LinkedInChannel
from src.channels.web_form import WebFormChannel, WebFormSubmission
from src.channels.whatsapp import WhatsAppChannel, WhatsAppMessage


def print_separator(char="─", width=60):
    print(char * width)


def print_result(result):
    print_separator()
    print(f"Acao: {result.action}")
    print(f"Lead ID: {result.lead_id or 'N/A'}")
    print(f"Resumo: {result.summary}")
    if result.alerts:
        print("\nAlertas:")
        for alert in result.alerts:
            print(f"  ! {alert}")
    if result.next_steps:
        print("\nProximas acoes:")
        for i, step in enumerate(result.next_steps, 1):
            print(f"  {i}. {step}")
    print_separator()


def cmd_ingest(args, orchestrator: LeadOrchestrator):
    """Processa novo lead a partir de texto livre."""
    raw_input = args.input
    channel = args.channel or "manual"
    print(f"\nProcessando novo lead via {channel}...")
    result = orchestrator.ingest_lead(raw_input, channel)
    print_result(result)


def cmd_qualify_all(args, orchestrator: LeadOrchestrator):
    """Qualifica todos os leads pendentes."""
    print("\nQualificando todos os leads pendentes...")
    results = orchestrator.qualify_pending()
    if not results:
        print("Nenhum lead pendente encontrado.")
        return
    print(f"\n{len(results)} lead(s) qualificado(s):")
    for result in results:
        print_result(result)


def cmd_dashboard(args, orchestrator: LeadOrchestrator):
    """Exibe o dashboard consolidado."""
    dashboard = orchestrator.get_dashboard()
    stats = dashboard["stats"]

    print("\n" + "=" * 60)
    print("         DTS LEAD AGENT - DASHBOARD")
    print("=" * 60)
    print(f"\nTotal de leads: {stats['total']}")

    print("\nPor status:")
    for status, count in stats.get("by_status", {}).items():
        print(f"  {status:<20} {count:>4}")

    print("\nPor canal:")
    for item in dashboard.get("top_channels", []):
        print(f"  {item['channel']:<20} {item['count']:>4}")

    qualified = dashboard.get("qualified_leads", [])
    print(f"\nLeads qualificados aguardando atendimento: {len(qualified)}")

    for lead in qualified[:5]:  # Top 5
        print(f"\n  [{lead['id']}] {lead['name']} | Score: {lead['score']}/100")
        print(f"       Plano: {lead['plan_type']} | Canal: {lead['channel']}")
        if lead.get("contact"):
            print(f"       Contato: {lead['contact']}")
        if lead.get("budget_range"):
            print(f"       Orçamento: {lead['budget_range']}")

    print("\n" + "=" * 60)


def cmd_qualified(args, orchestrator: LeadOrchestrator):
    """Lista leads qualificados em formato detalhado."""
    leads = orchestrator.get_qualified_leads()
    if not leads:
        print("\nNenhum lead qualificado no momento.")
        return

    print(f"\n{len(leads)} lead(s) qualificado(s) (ordenados por score):\n")
    for lead in leads:
        print_separator()
        print(f"ID: {lead['id']} | Score: {lead['score']}/100")
        print(f"Nome: {lead['name']}")
        if lead.get("company_name"):
            print(f"Empresa: {lead['company_name']}")
        print(f"Tipo de plano: {lead['plan_type']}")
        if lead.get("num_beneficiaries"):
            print(f"Beneficiários: {lead['num_beneficiaries']}")
        if lead.get("budget_range"):
            print(f"Orçamento: {lead['budget_range']}")
        if lead.get("decision_timeline"):
            print(f"Prazo: {lead['decision_timeline']}")
        if lead.get("contact"):
            print(f"Contato: {lead['contact']}")
        if lead.get("pain_points"):
            print(f"Dores: {', '.join(lead['pain_points'])}")
        if lead.get("notes"):
            print(f"Notas: {lead['notes']}")
    print_separator()


def cmd_respond(args, orchestrator: LeadOrchestrator):
    """Processa resposta de um lead."""
    lead_id = args.lead_id
    response = args.response
    channel = args.channel or "whatsapp"

    print(f"\nProcessando resposta do lead {lead_id} via {channel}...")
    result = orchestrator.process_lead_response(lead_id, response, channel)
    print_result(result)


def cmd_demo(args, orchestrator: LeadOrchestrator):
    """Executa demonstração com leads realistas do nicho executivo PJ."""
    print("\n" + "=" * 60)
    print("   DTS LEAD AGENT - DEMO: Executivos PJ + Familia")
    print("=" * 60)

    # Cenario 1: Lead quente — saiu ha 20 dias, portabilidade disponivel, filhos pequenos
    lead1 = WhatsAppChannel().format_for_agent(
        WhatsAppMessage(
            sender_name="Ricardo Alves",
            sender_number="+55 11 98765-4321",
            message_text=(
                "Ola! Fui demitido da Accenture ha 3 semanas, era Gerente Senior de TI. "
                "Abri minha consultoria (ja tenho CNPJ) e preciso de plano de saude urgente. "
                "Tenho esposa e dois filhos de 4 e 7 anos. Todos precisam de cobertura. "
                "Tinha plano Bradesco Saude nacional pela empresa. Quero manter o mesmo padrao."
            ),
        )
    )

    # Cenario 2: Lead morno — LinkedIn, executivo de financas, informacoes incompletas
    lead2 = LinkedInChannel().format_for_agent(
        LinkedInChannel().parse_lead_gen_form({
            "firstName": "Fernanda",
            "lastName": "Torres",
            "title": "CFO",
            "companyName": "FT Consultoria Financeira",
            "emailAddress": "fernanda.torres@ftconsultoria.com.br",
            "message": (
                "Vi a campanha de voces. Abri minha empresa de consultoria financeira "
                "ha 2 meses. Preciso de plano para mim e minha familia. "
                "Trabalhei 8 anos no Itau onde tinhamos SulAmerica."
            ),
            "campaign": "DTS-Executivos-PJ-LinkedIn-Q2",
        })
    )

    # Cenario 3: Formulario web — possivel fora do nicho (poucas informacoes de familia)
    lead3 = WebFormChannel().format_for_agent(
        WebFormSubmission(
            name="Marcos Vinicius",
            email="mv@mvengenharia.com.br",
            phone="(31) 99988-7766",
            company_name="MV Engenharia e Projetos ME",
            message=(
                "Quero plano de saude para minha empresa. "
                "Sou engenheiro civil, abri meu escritorio sozinho."
            ),
            plan_interest="PME",
            utm_source="google",
            utm_campaign="plano-saude-pj-engenheiros",
        )
    )

    demo_leads = [
        {"channel": "whatsapp",      "data": lead1, "label": "Lead QUENTE (portabilidade elegivel + filhos)"},
        {"channel": "linkedin",      "data": lead2, "label": "Lead MORNO (informacoes incompletas)"},
        {"channel": "formulario_web","data": lead3, "label": "Lead FRIO (possivel fora do nicho — 1 vida)"},
    ]

    for i, item in enumerate(demo_leads, 1):
        print(f"\n[Demo {i}/{len(demo_leads)}] {item['label']}")
        print(f"Canal: {item['channel']}")
        print_separator("-")
        result = orchestrator.ingest_lead(item["data"], item["channel"])
        print_result(result)

    print("\n--- Dashboard apos demo ---")
    cmd_dashboard(None, orchestrator)


def main():
    parser = argparse.ArgumentParser(
        description="DTS Lead Agent - Sistema de captação e qualificação de leads para planos de saúde"
    )
    parser.add_argument(
        "--storage",
        default="data/leads.json",
        help="Caminho para o arquivo de armazenamento de leads",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Modelo Claude a utilizar",
    )

    subparsers = parser.add_subparsers(dest="command")

    # ingest
    ingest_parser = subparsers.add_parser("ingest", help="Processa novo lead")
    ingest_parser.add_argument("input", help="Dados brutos do lead (texto livre)")
    ingest_parser.add_argument("--channel", help="Canal de origem (whatsapp, email, etc.)")

    # qualify-all
    subparsers.add_parser("qualify-all", help="Qualifica todos os leads pendentes")

    # dashboard
    subparsers.add_parser("dashboard", help="Exibe dashboard consolidado")

    # qualified
    subparsers.add_parser("qualified", help="Lista leads qualificados")

    # respond
    respond_parser = subparsers.add_parser("respond", help="Processa resposta de um lead")
    respond_parser.add_argument("lead_id", help="ID do lead")
    respond_parser.add_argument("response", help="Texto da resposta do lead")
    respond_parser.add_argument("--channel", help="Canal da resposta", default="whatsapp")

    # demo
    subparsers.add_parser("demo", help="Executa demonstração com leads simulados")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Erro: variável ANTHROPIC_API_KEY não definida.")
        print("Configure com: export ANTHROPIC_API_KEY='sua-chave'")
        sys.exit(1)

    orchestrator = LeadOrchestrator(storage_path=args.storage, model=args.model)

    commands = {
        "ingest": cmd_ingest,
        "qualify-all": cmd_qualify_all,
        "dashboard": cmd_dashboard,
        "qualified": cmd_qualified,
        "respond": cmd_respond,
        "demo": cmd_demo,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, orchestrator)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
