"""
Tool definitions para os agentes de leads — DTS
Nicho: executivos ex-CLT que abriram PJ, precisam de plano para si + família (3+ vidas).
"""

QUALIFICATION_TOOLS = [
    {
        "name": "buscar_lead",
        "description": "Busca os dados completos de um lead pelo ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "atualizar_perfil_executivo",
        "description": (
            "Atualiza os dados de perfil do executivo PJ: informações sobre a saída da empresa, "
            "CNPJ, composição familiar e plano anterior. Use sempre que coletar novas informações."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "former_company": {"type": "string", "description": "Empresa de onde o executivo saiu"},
                "former_job_title": {"type": "string", "description": "Cargo que ocupava"},
                "left_company_date": {
                    "type": "string",
                    "description": "Data de saída no formato AAAA-MM-DD ou AAAA-MM",
                },
                "has_cnpj": {"type": "boolean", "description": "Já tem CNPJ aberto?"},
                "company_name": {"type": "string", "description": "Nome da empresa PJ aberta"},
                "cnpj": {"type": "string"},
                "had_corporate_plan": {
                    "type": "boolean",
                    "description": "Tinha plano de saúde pela empresa anterior?",
                },
                "previous_operator": {
                    "type": "string",
                    "description": "Operadora do plano anterior (Bradesco, SulAmérica, Unimed, etc.)",
                },
                "previous_plan_coverage": {
                    "type": "string",
                    "enum": ["nacional", "estadual", "regional", "desconhecido"],
                    "description": "Abrangência geográfica do plano anterior",
                },
                "previous_plan_name": {"type": "string", "description": "Nome ou código do plano anterior"},
                "reason_for_leaving": {
                    "type": "string",
                    "description": "Contexto da saída: demissão, pedido de demissão, aposentadoria, empreendimento",
                },
                "annual_revenue_estimate": {
                    "type": "string",
                    "description": "Faixa de faturamento anual PJ (ex: 'até R$ 120k', 'R$ 300-500k')",
                },
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "atualizar_familia",
        "description": (
            "Atualiza dados sobre a composição familiar. "
            "CRÍTICO: o nicho exige mínimo de 3 vidas. Se tiver menos, desqualificar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "num_family_members": {
                    "type": "integer",
                    "description": "Total de vidas incluindo o titular (mínimo 3 para o nicho)",
                },
                "family_composition": {
                    "type": "string",
                    "description": "Ex: 'titular + cônjuge + 2 filhos'",
                },
                "children_ages": {
                    "type": "string",
                    "description": "Idades dos filhos, relevante para carências e urgência",
                },
                "has_children_under_12": {
                    "type": "boolean",
                    "description": "Tem filhos menores de 12 anos? Aumenta urgência significativamente",
                },
                "wants_dental": {
                    "type": "boolean",
                    "description": "Tem interesse em plano odontológico junto?",
                },
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "atualizar_interesse_plano",
        "description": "Atualiza preferências e orçamento para o novo plano.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "desired_coverage": {
                    "type": "string",
                    "enum": ["nacional", "estadual", "regional", "desconhecido"],
                },
                "desired_accommodation": {
                    "type": "string",
                    "enum": ["apartamento", "enfermaria", "sem_preferencia"],
                    "description": "Executivos geralmente querem apartamento (padrão anterior)",
                },
                "budget_range": {
                    "type": "string",
                    "description": "Faixa de orçamento total mensal para todos os beneficiários",
                },
                "urgency_level": {
                    "type": "string",
                    "enum": ["imediata", "até 30 dias", "até 60 dias", "sem urgência"],
                },
                "can_deduct_as_pj_expense": {
                    "type": "boolean",
                    "description": "Sabe que pode deduzir o plano como despesa da empresa PJ?",
                },
            },
            "required": ["lead_id"],
        },
    },
    {
        "name": "avaliar_portabilidade",
        "description": (
            "Avalia se o lead é elegível para portabilidade de carências (ANS). "
            "Regra: até 60 dias após a demissão / rescisão do vínculo empregatício. "
            "Se elegível, é um gatilho de urgência FORTÍSSIMO — use isso como argumento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "portability_status": {
                    "type": "string",
                    "enum": ["elegivel", "expirado", "nao_aplica", "desconhecido"],
                },
                "portability_deadline": {
                    "type": "string",
                    "description": "Data limite para portabilidade (AAAA-MM-DD)",
                },
                "days_remaining": {
                    "type": "integer",
                    "description": "Dias restantes para a portabilidade",
                },
            },
            "required": ["lead_id", "portability_status"],
        },
    },
    {
        "name": "calcular_score",
        "description": (
            "Calcula o score de qualificação (0-100) usando critérios BANT adaptados ao nicho "
            "de executivo PJ + família. Score >= 60 = qualificado para cotação imediata."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "score": {"type": "integer", "minimum": 0, "maximum": 100},
                "score_breakdown": {
                    "type": "object",
                    "description": "Pontuação por dimensão",
                    "properties": {
                        "budget": {
                            "type": "integer",
                            "description": "0-25: orçamento e capacidade financeira (PJ deduz como despesa)",
                        },
                        "authority": {
                            "type": "integer",
                            "description": "0-20: decisor (dono de PJ = sempre sim, mas confirmar)",
                        },
                        "need": {
                            "type": "integer",
                            "description": "0-30: necessidade (3+ vidas, filhos pequenos, sem plano atual)",
                        },
                        "timeline": {
                            "type": "integer",
                            "description": "0-25: urgência (portabilidade, filhos, situação atual sem plano)",
                        },
                    },
                },
                "justification": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["qualificado", "desqualificado", "qualificando"],
                },
                "disqualification_reason": {
                    "type": "string",
                    "description": "Se desqualificado, o motivo (ex: menos de 3 vidas, não tem PJ)",
                },
            },
            "required": ["lead_id", "score", "score_breakdown", "justification", "status"],
        },
    },
    {
        "name": "registrar_interacao",
        "description": "Registra uma interação com o lead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "channel": {"type": "string"},
                "message": {"type": "string"},
                "direction": {"type": "string", "enum": ["inbound", "outbound"]},
            },
            "required": ["lead_id", "channel", "message", "direction"],
        },
    },
    {
        "name": "gerar_mensagem_qualificacao",
        "description": (
            "Gera mensagem personalizada para coletar informações de qualificação. "
            "Deve soar como um consultor especializado, não como um formulário. "
            "Mencionar portabilidade se houver urgência de prazo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp", "email", "linkedin"],
                },
                "missing_info": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Campos críticos ainda ausentes",
                },
                "highlight_portability": {
                    "type": "boolean",
                    "description": "Se true, mencionar urgência da portabilidade na mensagem",
                },
            },
            "required": ["lead_id", "channel", "missing_info"],
        },
    },
]


DISCOVERY_TOOLS = [
    {
        "name": "criar_lead",
        "description": (
            "Cria um novo lead no sistema. Para o nicho executivo PJ, extraia o máximo de "
            "informações disponíveis sobre o perfil profissional e situação familiar."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp", "linkedin", "formulario_web", "email", "telefone", "indicacao", "manual"],
                },
                "phone": {"type": "string"},
                "email": {"type": "string"},
                "whatsapp": {"type": "string"},
                "former_company": {"type": "string", "description": "Empresa de onde saiu"},
                "former_job_title": {"type": "string", "description": "Cargo anterior"},
                "left_company_date": {"type": "string", "description": "Data de saída AAAA-MM-DD"},
                "has_cnpj": {"type": "boolean"},
                "company_name": {"type": "string"},
                "num_family_members": {
                    "type": "integer",
                    "description": "Quantas pessoas no plano (titular + família)",
                },
                "had_corporate_plan": {"type": "boolean"},
                "previous_operator": {"type": "string"},
                "raw_message": {"type": "string", "description": "Mensagem original do lead"},
            },
            "required": ["name", "channel"],
        },
    },
    {
        "name": "listar_leads_novos",
        "description": "Lista todos os leads com status 'novo'.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "obter_estatisticas",
        "description": "Retorna estatísticas gerais dos leads.",
        "input_schema": {"type": "object", "properties": {}},
    },
]
