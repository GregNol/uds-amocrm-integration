"""Парсеры вебхуков UDS в NormalizedEvent.

UDS шлёт события на три разных пути:
  POST /api/v2/events/operation    — транзакция (покупка)
  POST /api/v2/events/participant  — новый клиент
  POST /api/v2/events/order        — заказ (UDS Goods), со статусами

В payload нет телефона/email — только id клиента. Контакты дотягиваются
отдельно через GET /customers/{id} (см. app/uds/client.py), здесь только
нормализация структуры события.
"""
import logging

from app.schemas import Customer, EventType, NormalizedEvent

logger = logging.getLogger(__name__)

# В операциях GOODS_PURCHASE приходит ещё и как отдельный заказ (webhook order),
# поэтому из операций берём только обычные покупки, чтобы не плодить дубли сделок.
_OPERATION_PURCHASE_ACTIONS = {"PURCHASE"}

# Заказы создаём как открытую сделку; закрытие — за менеджерами вручную
# (UDS не шлёт вебхук при завершении заказа), поэтому COMPLETED/DELETED пропускаем.
_ORDER_OPEN_STATES = {"NEW", "WAITING_PAYMENT", "NEED_ACK"}


def parse_operation(payload: dict, request_id: str) -> NormalizedEvent | None:
    """Транзакция -> покупка. Берём только action=PURCHASE, state=NORMAL."""
    if payload.get("action") not in _OPERATION_PURCHASE_ACTIONS:
        logger.info("operation action=%s пропущен", payload.get("action"))
        return None
    if payload.get("state", "NORMAL") != "NORMAL":
        return None

    c = payload.get("customer") or {}
    if not c.get("id"):
        logger.warning("operation без customer.id: %s", payload)
        return None

    return NormalizedEvent(
        event_id=request_id,
        event_type=EventType.PURCHASE,
        customer=Customer(uds_customer_id=str(c["id"]), name=c.get("displayName")),
        amount=payload.get("total"),
        source="UDS",
    )


def parse_participant(payload: dict, request_id: str) -> NormalizedEvent | None:
    """Новый клиент.

    Реальный payload — объект клиента: id в participant.id, а телефон/email/имя
    на верхнем уровне (обогащение из API не требуется).
    """
    cid = (payload.get("participant") or {}).get("id") or payload.get("id")
    if not cid:
        logger.warning("participant без id: %s", payload)
        return None
    return NormalizedEvent(
        event_id=request_id,
        event_type=EventType.NEW_CUSTOMER,
        customer=Customer(
            uds_customer_id=str(cid),
            name=payload.get("displayName"),
            phone=payload.get("phone"),
            email=payload.get("email"),
            channel=payload.get("channelName"),
        ),
        source="UDS",
    )


def parse_order(payload: dict, request_id: str) -> NormalizedEvent | None:
    """Заказ UDS Goods -> создаём открытую сделку.

    NEW/WAITING_PAYMENT/NEED_ACK -> сделка (open). Остальные статусы
    (COMPLETED, DELETED, ...) пропускаем — закрытие за менеджерами.
    """
    oid = payload.get("id")
    if not oid:
        logger.warning("order без id: %s", payload)
        return None
    state = payload.get("state")

    if state not in _ORDER_OPEN_STATES:
        logger.info("order state=%s пропущен", state)
        return None
    event_type = EventType.ORDER

    c = payload.get("customer") or {}
    if not c.get("id"):
        logger.warning("order без customer.id: %s", payload)
        return None

    # Телефон/имя получателя есть прямо в заказе (delivery) — берём оттуда.
    delivery = payload.get("delivery") or {}
    return NormalizedEvent(
        event_id=request_id,
        event_type=event_type,
        customer=Customer(
            uds_customer_id=str(c["id"]),
            name=c.get("displayName") or delivery.get("receiverName"),
            phone=delivery.get("receiverPhone"),
        ),
        order_id=str(oid),
        order_state=state,
        amount=payload.get("total"),
        source="UDS Goods",
    )
