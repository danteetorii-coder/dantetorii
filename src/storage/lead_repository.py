import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.lead import Lead, LeadChannel, LeadStatus


class LeadRepository:
    def __init__(self, storage_path: str = "data/leads.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._leads: dict[str, Lead] = {}
        self._load()

    def _load(self):
        if self.storage_path.exists():
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._leads = {k: Lead.from_dict(v) for k, v in data.items()}

    def _save(self):
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: v.to_dict() for k, v in self._leads.items()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def create(self, name: str, channel: LeadChannel, **kwargs) -> Lead:
        lead_id = str(uuid.uuid4())[:8]
        lead = Lead(id=lead_id, name=name, channel=channel, **kwargs)
        self._leads[lead_id] = lead
        self._save()
        return lead

    def get(self, lead_id: str) -> Optional[Lead]:
        return self._leads.get(lead_id)

    def update(self, lead: Lead) -> Lead:
        lead.updated_at = datetime.now()
        self._leads[lead.id] = lead
        self._save()
        return lead

    def list_by_status(self, status: LeadStatus) -> list[Lead]:
        return [l for l in self._leads.values() if l.status == status]

    def list_all(self) -> list[Lead]:
        return list(self._leads.values())

    def get_stats(self) -> dict:
        leads = self.list_all()
        stats = {"total": len(leads), "by_status": {}, "by_channel": {}}
        for lead in leads:
            stats["by_status"][lead.status.value] = stats["by_status"].get(lead.status.value, 0) + 1
            stats["by_channel"][lead.channel.value] = stats["by_channel"].get(lead.channel.value, 0) + 1
        return stats
