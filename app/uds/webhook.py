"""Парсинг сырого вебхука UDS в NormalizedEvent.

ВАЖНО: формат вебхука зависит от настроек UDS. Ниже — разумное допущение
по структуре. После получения первого реального вебхука (он логируется в
event_log.payload) поправим маппинг под факт. Места для правки помечены TODO.
"""
import logging

from app.schemas import Customer, EventType, NormalizedEvent

logger = logging.getLogger(__name__)

# Маппинг типа события UDS -> наш EventType. TODO: сверить названия с UDS.
_TYPE_MAP = {
    "customer.created": EventType.NEW_CUSTOMER,
    "new_customer": EventType.NEW_CUSTOMER,
    "purchase": EventType.PURCHASE,
    "purchase.created": EventType.PURCHASE,
    "order": EventType.ORDER,
    "order.created": EventType.ORDER,
}


def parse_webhook(payload: dict) -> NormalizedEvent | None:
    """Привести сырой payload UDS к NormalizedEvent. None — событие игнорируем."""
    raw_type = str(payload.get("type") or payload.get("event") or "").lower()
    event_type = _TYPE_MAP.get(raw_type)
    if event_type is None:
        logger.info("Неизвестный тип события UDS: %r — пропускаем", raw_type)
        return None

    # TODO: подогнать пути извлечения под реальную структуру вебхука UDS.
    data = payload.get("data", payload)
    customer_data = data.get("customer", data)

    customer = Customer(
        uds_customer_id=str(
            customer_data.get("id") or customer_data.get("customerId") or ""
        ),
        name=customer_data.get("displayName") or customer_data.get("name"),
        phone=customer_data.get("phone"),
        email=customer_data.get("email"),
    )

    event_id = str(
        payload.get("id")
        or data.get("id")
        or data.get("operationId")
        or ""
    )
    if not event_id or not customer.uds_customer_id:
        logger.warning("В вебхуке нет event_id или customer_id: %s", payload)
        return None

    return NormalizedEvent(
        event_id=event_id,
        event_type=event_type,
        customer=customer,
        order_id=str(data["orderId"]) if data.get("orderId") else None,
        amount=data.get("total") or data.get("amount"),
        source="UDS",
    )
