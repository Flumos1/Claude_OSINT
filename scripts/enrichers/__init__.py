"""Энричеры (архитектура по мотивам flowsint). Импорт регистрирует их в REGISTRY."""
from . import (  # noqa: F401
    domain_enr,
    email_enr,
    email_leaks_enr,
    ip_enr,
    nazk_enr,
    opendatabot_enr,
    phone_enr,
    prozorro_enr,
    ru_company_enr,
    ua_company_enr,
    ua_person_enr,
    username_enr,
)
from .base import ENTITY_TYPES, EnricherResult, enrichers_for  # noqa: F401
