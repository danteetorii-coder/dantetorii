"""
Tool definitions for the lead qualification agent.
These are passed to the Claude API as tools (function calling).
"""

QUALIFICATION_TOOLS = [
    {
        "name": "atualizar_lead",
        "description": (
            "Atualiza os dados de um lead com informações coletadas durante a qualificação. "
            "Use sempre que identificar novas informações relevantes sobre o lead."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "ID único do lead"},
                "plan_type": {
                    "type": "string",
                    "enum": ["individual", "familiar", "pme", "empresarial", "odontologico", "desconhecido"],
                    "description": "Tipo de plano de interesse",
                },
                "num_beneficiaries": {
                    "type": "integer",
                    "description": "Número de vidas/beneficiários a incluir no plano",
                },
                "company_size": {
                    "type": "integer",
                    "description": "Número de funcionários da empresa (para planos PJ)",
                },
                "budget_range": {
                    "type": "string",
                    "description": "Faixa de orçamento mensal (ex: 'até R$ 300/vida', 'R$ 500-800/vida')",
                },
                "current_operator": {
                    "type": "string",
                    "description": "Operadora de saúde atual do lead, se houver",
                },
                "decision_timeline": {
                    "type": "string",
                    "enum": ["imediato", "30 dias", "3 meses", "6 meses", "sem prazo definido"],
                    "description": "Prazo para tomar a decisão de contratar",
                },
                "is_decision_maker": {
                    "type": "boolean",
                    "description": "Se o contato é o tomador de decisão final",
                },
                "desired_coverage": {
                    "type": "string",
                    "description": "Cobertura geográfica desejada (nacional, regional, estadual)",
                },
                "pain_points": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Principais dores/problemas que o lead quer resolver",
                },
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "calcular_score",
        "description": (
            "Calcula o score de qualificação do lead de 0 a 100 baseado nos dados coletados. "
            "Um lead é considerado qualificado quando score >= 60."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "ID único do lead"},
                "score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Score de 0 a 100 baseado nos critérios BANT",
                },
                "justification": {
                    "type": "string",
                    "description": "Justificativa detalhada do score atribuído",
                },
                "status": {
                    "type": "string",
                    "enum": ["qualificado", "desqualificado", "qualificando"],
                    "description": "Status resultante da qualificação",
                },
            },
            "required": ["lead_id", "score", "justification", "status"],
        },
    },
    {
        "name": "registrar_interacao",
        "description": "Registra uma interação com o lead (mensagem enviada ou recebida).",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "channel": {
                    "type": "string",
                    "description": "Canal da interação (whatsapp, email, telefone, etc.)",
                },
                "message": {"type": "string", "description": "Conteúdo da mensagem"},
                "direction": {
                    "type": "string",
                    "enum": ["inbound", "outbound"],
                    "description": "inbound = recebido do lead, outbound = enviado ao lead",
                },
            },
            "required": ["lead_id", "channel", "message", "direction"],
        },
    },
    {
        "name": "buscar_lead",
        "description": "Busca os dados completos de um lead pelo ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string", "description": "ID único do lead"},
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "gerar_mensagem_qualificacao",
        "description": (
            "Gera uma mensagem personalizada para enviar ao lead com o objetivo de "
            "coletar informações de qualificação de forma natural e não invasiva."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp", "email", "linkedin"],
                    "description": "Canal pelo qual a mensagem será enviada",
                },
                "missing_info": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de informações ainda ausentes que precisam ser coletadas",
                },
            },
            "required": ["lead_id", "channel", "missing_info"],
        },
    },
]

DISCOVERY_TOOLS = [
    {
        "name": "criar_lead",
        "description": "Cria um novo lead no sistema a partir de dados coletados em algum canal.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nome completo do lead"},
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp", "linkedin", "formulario_web", "email", "telefone", "indicacao", "manual"],
                    "description": "Canal de origem do lead",
                },
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "whatsapp": {"type": "string"},
                "company_name": {"type": "string"},
                "plan_type": {
                    "type": "string",
                    "enum": ["individual", "familiar", "pme", "empresarial", "odontologico", "desconhecido"],
                },
                "raw_message": {
                    "type": "string",
                    "description": "Mensagem original recebida do lead, se houver",
                },
            },
            "required": ["name", "channel"],
        },
    },
    {
        "name": "listar_leads_novos",
        "description": "Lista todos os leads com status 'novo' que ainda não foram qualificados.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "obter_estatisticas",
        "description": "Retorna estatísticas gerais sobre os leads no sistema.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]
