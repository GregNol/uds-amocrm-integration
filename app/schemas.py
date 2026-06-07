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
    channel: str | None = None  # канал привлечения UDS (channelName) -> "Источник"


class NormalizedEvent(BaseModel):
    event_id: str  # X-Origin-Request-Id вебхука — ключ идемпотентности
    event_type: EventType
    customer: Customer
    order_id: str | None = None  # для purchase/order
    order_state: str | None = None  # NEW / COMPLETED / ... (для заказов)
    amount: float | None = None  # сумма (total)
    source: str | None = "UDS"
    note: str | None = None  # служебное примечание в сделку amoCRM
