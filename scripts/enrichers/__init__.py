"""Энричеры (архитектура по мотивам flowsint). Импорт регистрирует их в REGISTRY."""
from . import (  # noqa: F401
    domain_enr,
    email_enr,
    ip_enr,
    opendatabot_enr,
    ru_company_enr,
    ua_company_enr,
    ua_person_enr,
)
from .base import ENTITY_TYPES, EnricherResult, enrichers_for  # noqa: F401
