"""
Testes unitários para o DTS Lead Agent.
Não requerem chave da API (usam mocks).
"""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from src.models.lead import Lead, LeadChannel, LeadStatus, PlanType
from src.storage.lead_repository import LeadRepository


class TestLeadModel(unittest.TestCase):
    def test_lead_creation(self):
        lead = Lead(id="abc123", name="João Silva", channel=LeadChannel.WHATSAPP)
        self.assertEqual(lead.name, "João Silva")
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.score, 0)

    def test_lead_serialization(self):
        lead = Lead(id="abc123", name="Maria Santos", channel=LeadChannel.EMAIL)
        lead.email = "maria@email.com"
        lead.score = 75
        lead.status = LeadStatus.QUALIFIED

        data = lead.to_dict()
        self.assertEqual(data["name"], "Maria Santos")
        self.assertEqual(data["score"], 75)
        self.assertEqual(data["status"], "qualificado")

        restored = Lead.from_dict(data)
        self.assertEqual(restored.name, lead.name)
        self.assertEqual(restored.score, lead.score)
        self.assertEqual(restored.status, lead.status)

    def test_add_interaction(self):
        lead = Lead(id="xyz789", name="Pedro Lima", channel=LeadChannel.LINKEDIN)
        lead.add_interaction("linkedin", "Olá, tenho interesse!", "inbound")
        self.assertEqual(len(lead.interactions), 1)
        self.assertEqual(lead.interactions[0]["direction"], "inbound")


class TestLeadRepository(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.tmp_dir, "test_leads.json")
        self.repo = LeadRepository(self.storage_path)

    def test_create_and_get(self):
        lead = self.repo.create("Teste Lead", LeadChannel.WEB_FORM)
        fetched = self.repo.get(lead.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Teste Lead")

    def test_update(self):
        lead = self.repo.create("Update Test", LeadChannel.PHONE)
        lead.score = 80
        lead.status = LeadStatus.QUALIFIED
        self.repo.update(lead)

        fetched = self.repo.get(lead.id)
        self.assertEqual(fetched.score, 80)
        self.assertEqual(fetched.status, LeadStatus.QUALIFIED)

    def test_list_by_status(self):
        self.repo.create("Lead 1", LeadChannel.WHATSAPP)
        lead2 = self.repo.create("Lead 2", LeadChannel.EMAIL)
        lead2.status = LeadStatus.QUALIFIED
        self.repo.update(lead2)

        new_leads = self.repo.list_by_status(LeadStatus.NEW)
        qualified_leads = self.repo.list_by_status(LeadStatus.QUALIFIED)

        self.assertEqual(len(new_leads), 1)
        self.assertEqual(len(qualified_leads), 1)

    def test_persistence(self):
        lead = self.repo.create("Persistent Lead", LeadChannel.LINKEDIN)
        lead_id = lead.id

        repo2 = LeadRepository(self.storage_path)
        fetched = repo2.get(lead_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Persistent Lead")

    def test_get_stats(self):
        self.repo.create("Lead A", LeadChannel.WHATSAPP)
        self.repo.create("Lead B", LeadChannel.WHATSAPP)
        lead_c = self.repo.create("Lead C", LeadChannel.EMAIL)
        lead_c.status = LeadStatus.QUALIFIED
        self.repo.update(lead_c)

        stats = self.repo.get_stats()
        self.assertEqual(stats["total"], 3)
        self.assertEqual(stats["by_channel"]["whatsapp"], 2)
        self.assertEqual(stats["by_channel"]["email"], 1)


class TestChannelParsers(unittest.TestCase):
    def test_whatsapp_extract_info(self):
        from src.channels.whatsapp import WhatsAppMessage

        msg = WhatsAppMessage(
            sender_name="Carlos",
            sender_number="+55 11 99999-0000",
            message_text="Tenho 50 funcionários e preciso de plano de saúde. Email: carlos@empresa.com",
        )
        info = msg.extract_info()
        self.assertEqual(info["name"], "Carlos")
        self.assertEqual(info["num_beneficiaries"], 50)
        self.assertEqual(info["email"], "carlos@empresa.com")

    def test_web_form_parsing(self):
        from src.channels.web_form import WebFormChannel

        channel = WebFormChannel()
        submission = channel.parse_submission({
            "nome": "Ana Silva",
            "email": "ana@empresa.com",
            "funcionarios": 30,
            "mensagem": "Quero cotar plano PME",
        })
        self.assertEqual(submission.name, "Ana Silva")
        self.assertEqual(submission.num_employees, 30)

    def test_linkedin_lead_gen_form(self):
        from src.channels.linkedin import LinkedInChannel

        channel = LinkedInChannel()
        lead = channel.parse_lead_gen_form({
            "firstName": "Roberto",
            "lastName": "Silva",
            "title": "Diretor de RH",
            "companyName": "Empresa XYZ",
            "companySizeRange": "201-500",
            "emailAddress": "roberto@xyz.com",
        })
        self.assertEqual(lead.full_name.strip(), "Roberto Silva")
        self.assertEqual(lead.job_title, "Diretor de RH")
        estimated = lead.estimate_company_size()
        self.assertEqual(estimated, 350)


if __name__ == "__main__":
    unittest.main()
