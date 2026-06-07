"""Нормализованные модели событий — внутренний контракт между UDS и бизнес-логикой.

Сырой вебхук UDS приводим к этим структурам в app/uds/webhook.py,
поэтому бизнес-логика не зависит от формата UDS.
"""
from enum import StrEnum

from pydantic import BaseModel


class EventType(StrEnum):
    NEW_CUSTOMER = "new_customer"
    PURCHASE = "purchase"
    ORDER = "order"


class Customer(BaseModel):
    uds_customer_id: str
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class NormalizedEvent(BaseModel):
    event_id: str  # уникальный ID операции UDS — ключ идемпотентности
    event_type: EventType
    customer: Customer
    order_id: str | None = None  # для purchase/order
    amount: float | None = None  # сумма
    source: str | None = "UDS"
