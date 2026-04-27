"""
Testes unitários — DTS Lead Agent
Nicho: executivos ex-CLT que abriram PJ, precisam de plano para si + família (3+ vidas).
Não requerem chave da API (sem chamadas ao Claude).
"""

import os
import tempfile
import unittest
from datetime import date, timedelta

from src.models.lead import Lead, LeadChannel, LeadStatus, PlanType, PortabilityStatus
from src.storage.lead_repository import LeadRepository


class TestLeadModel(unittest.TestCase):

    def _make_lead(self, **kwargs) -> Lead:
        defaults = {"id": "test01", "name": "Teste", "channel": LeadChannel.WHATSAPP}
        defaults.update(kwargs)
        return Lead(**defaults)

    def test_defaults(self):
        lead = self._make_lead()
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.score, 0)
        self.assertEqual(lead.plan_type, PlanType.UNKNOWN)
        self.assertEqual(lead.portability_status, PortabilityStatus.UNKNOWN)

    def test_serialization_roundtrip(self):
        lead = self._make_lead(
            name="Ricardo Alves",
            channel=LeadChannel.LINKEDIN,
            former_company="Accenture",
            former_job_title="Gerente Senior TI",
            left_company_date="2026-04-07",
            has_cnpj=True,
            num_family_members=4,
            family_composition="titular + conjuge + 2 filhos",
            has_children_under_12=True,
            previous_operator="Bradesco Saude",
            portability_status=PortabilityStatus.ELIGIBLE,
            score=78,
            status=LeadStatus.QUALIFIED,
        )
        data = lead.to_dict()
        restored = Lead.from_dict(data)

        self.assertEqual(restored.name, lead.name)
        self.assertEqual(restored.former_company, "Accenture")
        self.assertEqual(restored.num_family_members, 4)
        self.assertEqual(restored.has_children_under_12, True)
        self.assertEqual(restored.portability_status, PortabilityStatus.ELIGIBLE)
        self.assertEqual(restored.score, 78)
        self.assertEqual(restored.status, LeadStatus.QUALIFIED)

    def test_is_minimum_viable_true(self):
        lead = self._make_lead(num_family_members=3)
        self.assertTrue(lead.is_minimum_viable())

    def test_is_minimum_viable_false(self):
        lead = self._make_lead(num_family_members=2)
        self.assertFalse(lead.is_minimum_viable())

    def test_is_minimum_viable_uses_num_beneficiaries_fallback(self):
        lead = self._make_lead(num_beneficiaries=4)
        self.assertTrue(lead.is_minimum_viable())

    def test_is_minimum_viable_none(self):
        lead = self._make_lead()
        self.assertFalse(lead.is_minimum_viable())

    def test_portability_window_within(self):
        left_date = (date.today() - timedelta(days=30)).isoformat()
        lead = self._make_lead(left_company_date=left_date)
        self.assertTrue(lead.is_within_portability_window())

    def test_portability_window_expired(self):
        left_date = (date.today() - timedelta(days=70)).isoformat()
        lead = self._make_lead(left_company_date=left_date)
        self.assertFalse(lead.is_within_portability_window())

    def test_portability_window_unknown(self):
        lead = self._make_lead()
        self.assertIsNone(lead.is_within_portability_window())

    def test_days_since_leaving(self):
        left_date = (date.today() - timedelta(days=20)).isoformat()
        lead = self._make_lead(left_company_date=left_date)
        days = lead.days_since_leaving_company()
        self.assertAlmostEqual(days, 20, delta=1)

    def test_add_interaction(self):
        lead = self._make_lead()
        lead.add_interaction("whatsapp", "Preciso de plano", "inbound")
        self.assertEqual(len(lead.interactions), 1)
        self.assertEqual(lead.interactions[0]["direction"], "inbound")
        self.assertEqual(lead.interactions[0]["channel"], "whatsapp")


class TestLeadRepository(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, "test_leads.json")
        self.repo = LeadRepository(self.storage_path)

    def test_create_and_get(self):
        lead = self.repo.create("Fernanda Torres", LeadChannel.LINKEDIN)
        fetched = self.repo.get(lead.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Fernanda Torres")

    def test_update_niche_fields(self):
        lead = self.repo.create("Carlos Souza", LeadChannel.WHATSAPP)
        lead.former_company = "Itau"
        lead.former_job_title = "Diretor de Tecnologia"
        lead.num_family_members = 4
        lead.portability_status = PortabilityStatus.ELIGIBLE
        lead.score = 85
        lead.status = LeadStatus.QUALIFIED
        self.repo.update(lead)

        fetched = self.repo.get(lead.id)
        self.assertEqual(fetched.former_company, "Itau")
        self.assertEqual(fetched.former_job_title, "Diretor de Tecnologia")
        self.assertEqual(fetched.num_family_members, 4)
        self.assertEqual(fetched.portability_status, PortabilityStatus.ELIGIBLE)
        self.assertEqual(fetched.score, 85)

    def test_list_by_status(self):
        self.repo.create("Lead 1", LeadChannel.WHATSAPP)
        lead2 = self.repo.create("Lead 2", LeadChannel.LINKEDIN)
        lead2.status = LeadStatus.QUALIFIED
        self.repo.update(lead2)
        lead3 = self.repo.create("Lead 3", LeadChannel.EMAIL)
        lead3.status = LeadStatus.DISQUALIFIED
        self.repo.update(lead3)

        self.assertEqual(len(self.repo.list_by_status(LeadStatus.NEW)), 1)
        self.assertEqual(len(self.repo.list_by_status(LeadStatus.QUALIFIED)), 1)
        self.assertEqual(len(self.repo.list_by_status(LeadStatus.DISQUALIFIED)), 1)

    def test_persistence(self):
        lead = self.repo.create("Persistente", LeadChannel.EMAIL)
        lead.former_company = "Microsoft"
        lead.num_family_members = 5
        self.repo.update(lead)
        lead_id = lead.id

        repo2 = LeadRepository(self.storage_path)
        fetched = repo2.get(lead_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.former_company, "Microsoft")
        self.assertEqual(fetched.num_family_members, 5)

    def test_get_stats(self):
        self.repo.create("A", LeadChannel.LINKEDIN)
        self.repo.create("B", LeadChannel.LINKEDIN)
        lead_c = self.repo.create("C", LeadChannel.WHATSAPP)
        lead_c.status = LeadStatus.QUALIFIED
        self.repo.update(lead_c)

        stats = self.repo.get_stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_channel"]["linkedin"], 2)
        self.assertEqual(stats["by_channel"]["whatsapp"], 1)
        self.assertEqual(stats["by_status"]["qualificado"], 1)


class TestChannelParsers(unittest.TestCase):

    def test_whatsapp_extract_portability_signal(self):
        from src.channels.whatsapp import WhatsAppMessage

        msg = WhatsAppMessage(
            sender_name="Ricardo",
            sender_number="+55 11 98765-0000",
            message_text=(
                "Fui demitido da Accenture ha 3 semanas. "
                "Tenho esposa e 2 filhos de 4 e 7 anos, somos 4 pessoas. "
                "Email: ricardo@consultoria.com"
            ),
        )
        info = msg.extract_info()
        self.assertEqual(info["name"], "Ricardo")
        self.assertEqual(info["num_beneficiaries"], 4)
        self.assertEqual(info["email"], "ricardo@consultoria.com")

    def test_linkedin_executive_profile_detection(self):
        from src.channels.linkedin import LinkedInChannel, LinkedInLead

        lead = LinkedInLead(
            full_name="Fernanda Torres",
            job_title="CFO",
            company="FT Consultoria",
            message="Abri minha consultoria financeira e preciso de plano",
        )
        self.assertTrue(lead.is_executive_profile())
        self.assertTrue(lead.has_transition_signal())

    def test_linkedin_non_executive(self):
        from src.channels.linkedin import LinkedInLead

        lead = LinkedInLead(
            full_name="Joao",
            job_title="Analista Junior",
            message="Quero cotar plano",
        )
        self.assertFalse(lead.is_executive_profile())

    def test_linkedin_lead_gen_form_parse(self):
        from src.channels.linkedin import LinkedInChannel

        channel = LinkedInChannel()
        lead = channel.parse_lead_gen_form({
            "firstName": "Fernanda",
            "lastName": "Torres",
            "title": "CFO",
            "companyName": "FT Consultoria",
            "companySizeRange": "1-10",
            "emailAddress": "ft@ftconsultoria.com",
            "campaign": "DTS-PJ-Q2",
        })
        self.assertEqual(lead.full_name.strip(), "Fernanda Torres")
        self.assertEqual(lead.job_title, "CFO")
        self.assertEqual(lead.estimate_company_size(), 5)

    def test_web_form_parsing(self):
        from src.channels.web_form import WebFormChannel

        channel = WebFormChannel()
        submission = channel.parse_submission({
            "nome": "Marcos Vinicius",
            "email": "mv@mv.com",
            "mensagem": "Quero plano para minha empresa",
        })
        self.assertEqual(submission.name, "Marcos Vinicius")
        self.assertEqual(submission.email, "mv@mv.com")


class TestOrchestratorAlerts(unittest.TestCase):
    """Testa a geração de alertas do orquestrador sem chamar a API."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, "test_leads.json")
        # Importa apenas o orquestrador, sem instanciar os agentes LLM
        from src.agents.orchestrator import LeadOrchestrator
        self.orchestrator = LeadOrchestrator.__new__(LeadOrchestrator)
        self.orchestrator.repository = LeadRepository(self.storage_path)

    def test_portability_alert_critical(self):
        from datetime import date, timedelta
        repo = self.orchestrator.repository
        lead = repo.create("Alerta Critico", LeadChannel.WHATSAPP)
        lead.left_company_date = (date.today() - timedelta(days=50)).isoformat()
        lead.portability_status = PortabilityStatus.ELIGIBLE
        repo.update(lead)

        alerts = self.orchestrator._build_alerts(lead)
        self.assertTrue(any("CRITICO" in a or "10" in a or "dias" in a for a in alerts))

    def test_minimum_viable_alert(self):
        repo = self.orchestrator.repository
        lead = repo.create("Poucas Vidas", LeadChannel.WHATSAPP)
        lead.num_family_members = 2
        repo.update(lead)

        alerts = self.orchestrator._build_alerts(lead)
        self.assertTrue(any("minimo" in a.lower() or "3" in a for a in alerts))

    def test_no_alerts_for_clean_lead(self):
        repo = self.orchestrator.repository
        lead = repo.create("Limpo", LeadChannel.LINKEDIN)
        lead.num_family_members = 4
        lead.portability_status = PortabilityStatus.NOT_APPLICABLE
        lead.status = LeadStatus.QUALIFIED
        repo.update(lead)

        alerts = self.orchestrator._build_alerts(lead)
        self.assertEqual(alerts, [])

    def test_next_steps_qualified(self):
        repo = self.orchestrator.repository
        lead = repo.create("Qualificado", LeadChannel.WHATSAPP)
        lead.status = LeadStatus.QUALIFIED
        lead.whatsapp = "+55 11 99999-0000"
        lead.portability_status = PortabilityStatus.ELIGIBLE
        lead.left_company_date = __import__("datetime").date.today().isoformat()
        lead.previous_operator = "Bradesco Saude"
        repo.update(lead)

        steps = self.orchestrator._get_next_steps(lead)
        self.assertTrue(any("portabilidade" in s.lower() for s in steps))
        self.assertTrue(any("Bradesco" in s for s in steps))

    def test_next_steps_disqualified(self):
        repo = self.orchestrator.repository
        lead = repo.create("Desqualificado", LeadChannel.WEB_FORM)
        lead.status = LeadStatus.DISQUALIFIED
        lead.raw_data["disqualification_reason"] = "menos de 3 vidas"
        repo.update(lead)

        steps = self.orchestrator._get_next_steps(lead)
        self.assertTrue(any("Arquivar" in s for s in steps))


if __name__ == "__main__":
    unittest.main()
