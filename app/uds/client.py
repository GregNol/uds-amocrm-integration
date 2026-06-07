"""Клиент UDS API (https://api.uds.app).

Используется как fallback/обогащение: если вебхук приносит только ID клиента,
здесь дотягиваем телефон/email/имя. Аутентификация — Basic:
login = UDS_COMPANY_ID, password = UDS_API_KEY.

ВНИМАНИЕ: точные пути эндпоинтов нужно сверить с актуальной докой UDS
для вашего тарифа. Помечено TODO.
"""
import base64
import logging

import httpx

from app.config import settings
from app.schemas import Customer

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.uds.app/partner/v2"


def _auth_header() -> str:
    raw = f"{settings.uds_company_id}:{settings.uds_api_key}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=_BASE_URL,
        headers={
            "Authorization": _auth_header(),
            "Accept": "application/json",
            "X-Origin-Request-Id": "uds-amocrm-integration",
        },
        timeout=30,
    )


async def get_customer(uds_customer_id: str) -> Customer | None:
    """Получить данные клиента по ID. TODO: сверить путь эндпоинта с докой UDS."""
    async with _client() as client:
        resp = await client.get(f"/customers/{uds_customer_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        # TODO: подогнать под реальную структуру ответа UDS
        return Customer(
            uds_customer_id=str(uds_customer_id),
            name=data.get("displayName") or data.get("name"),
            phone=data.get("phone"),
            email=data.get("email"),
        )
