"""Бизнес-логика синхронизации UDS -> amoCRM.

Три сценария:
  1) new_customer -> создать контакт (если нет)
  2) purchase     -> контакт + сделка + закрыть в "Успешно"
  3) order        -> контакт + сделка (стартовый статус)

Дедупликация контакта: сначала своя БД (customer_map), затем поиск в amoCRM
по телефону/email. Сделки переиспользуются по uds_order_id.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amocrm.client import AmoCRMClient
from app.config import settings
from app.models import CustomerMap, DealMap
from app.schemas import Customer, EventType, NormalizedEvent

logger = logging.getLogger(__name__)


async def resolve_contact(
    session: AsyncSession, amo: AmoCRMClient, customer: Customer
) -> int:
    """Вернуть amoCRM contact_id для клиента UDS, создав контакт при необходимости."""
    # 1. Уже знаем связку?
    existing = (
        await session.execute(
            select(CustomerMap).where(
                CustomerMap.uds_customer_id == customer.uds_customer_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing.amocrm_contact_id

    # 2. Ищем в amoCRM (по телефону, затем email)
    contact_id = await amo.find_contact(phone=customer.phone, email=customer.email)

    # 3. Не нашли — создаём
    if contact_id is None:
        contact_id = await amo.create_contact(
            name=customer.name or f"UDS {customer.uds_customer_id}",
            phone=customer.phone,
            email=customer.email,
        )
        logger.info("Создан контакт amoCRM id=%s", contact_id)

    session.add(
        CustomerMap(
            uds_customer_id=customer.uds_customer_id,
            amocrm_contact_id=contact_id,
            phone=customer.phone,
            email=customer.email,
        )
    )
    await session.commit()
    return contact_id


async def _get_or_create_deal(
    session: AsyncSession,
    amo: AmoCRMClient,
    event: NormalizedEvent,
    contact_id: int,
    status_id: int | None,
) -> DealMap:
    """Найти сделку по order_id или создать новую. order_id может отсутствовать."""
    if event.order_id:
        existing = (
            await session.execute(
                select(DealMap).where(DealMap.uds_order_id == event.order_id)
            )
        ).scalar_one_or_none()
        if existing:
            return existing

    deal_name = f"UDS заказ {event.order_id}" if event.order_id else "UDS покупка"
    # Источник = канал привлечения клиента из UDS, иначе фолбэк (UDS / UDS Goods).
    source = event.customer.channel or event.source
    lead_id = await amo.create_lead(
        name=deal_name,
        contact_id=contact_id,
        status_id=status_id,
        price=event.amount,
        source=source,
        order_id=event.order_id,
    )
    logger.info("Создана сделка amoCRM id=%s", lead_id)
    if event.note:
        await amo.add_note(lead_id, event.note)
    deal = DealMap(
        uds_order_id=event.order_id or f"evt:{event.event_id}",
        amocrm_lead_id=lead_id,
        status="open",
    )
    session.add(deal)
    await session.commit()
    return deal


async def handle_new_customer(
    session: AsyncSession, amo: AmoCRMClient, event: NormalizedEvent
) -> None:
    await resolve_contact(session, amo, event.customer)


async def handle_order(
    session: AsyncSession, amo: AmoCRMClient, event: NormalizedEvent
) -> None:
    contact_id = await resolve_contact(session, amo, event.customer)
    await _get_or_create_deal(
        session, amo, event, contact_id, settings.amocrm_status_new_id
    )


async def handle_purchase(
    session: AsyncSession, amo: AmoCRMClient, event: NormalizedEvent
) -> None:
    contact_id = await resolve_contact(session, amo, event.customer)
    deal = await _get_or_create_deal(
        session, amo, event, contact_id, settings.amocrm_status_won_id
    )
    # Закрываем сделку в "Успешно реализовано"
    if settings.amocrm_status_won_id and deal.status != "won":
        await amo.update_lead_status(deal.amocrm_lead_id, settings.amocrm_status_won_id)
        deal.status = "won"
        await session.commit()
        logger.info("Сделка amoCRM id=%s закрыта успешно", deal.amocrm_lead_id)


_HANDLERS = {
    EventType.NEW_CUSTOMER: handle_new_customer,
    EventType.ORDER: handle_order,
    EventType.PURCHASE: handle_purchase,
}


async def process_event(session: AsyncSession, event: NormalizedEvent) -> None:
    amo = AmoCRMClient(session)
    handler = _HANDLERS[event.event_type]
    await handler(session, amo, event)
