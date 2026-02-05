"""Domain entities for Bitrix24 CRM."""

from app.domain.entities.base import BitrixEntity, EntityType
from app.domain.entities.company import Company
from app.domain.entities.contact import Contact
from app.domain.entities.deal import Deal
from app.domain.entities.lead import Lead

__all__ = [
    "BitrixEntity",
    "EntityType",
    "Deal",
    "Contact",
    "Lead",
    "Company",
]
