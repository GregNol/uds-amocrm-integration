"""Клиент REST API amoCRM v4: контакты и сделки."""
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.amocrm.oauth import get_access_token
from app.config import settings

logger = logging.getLogger(__name__)

_retry = retry(
    retry=retry_if_exception_type(httpx.HTTPError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)


def _raise_for_status(resp: httpx.Response) -> None:
    """raise_for_status, но с телом ответа amoCRM в тексте ошибки (видно причину 400)."""
    if resp.is_error:
        raise httpx.HTTPStatusError(
            f"{resp.status_code} {resp.url}: {resp.text}",
            request=resp.request,
            response=resp,
        )


class AmoCRMClient:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _client(self) -> httpx.AsyncClient:
        access_token = await get_access_token(self.session)
        return httpx.AsyncClient(
            base_url=settings.amocrm_base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

    # ---------- Контакты ----------

    @_retry
    async def find_contact(self, *, phone: str | None, email: str | None) -> int | None:
        """Поиск контакта в amoCRM по телефону, затем по email. Возвращает ID или None."""
        async with await self._client() as client:
            for query in (phone, email):
                if not query:
                    continue
                resp = await client.get("/api/v4/contacts", params={"query": query})
                if resp.status_code == 204:  # ничего не найдено
                    continue
                _raise_for_status(resp)
                contacts = resp.json().get("_embedded", {}).get("contacts", [])
                if contacts:
                    return contacts[0]["id"]
        return None

    @_retry
    async def create_contact(
        self, *, name: str, phone: str | None, email: str | None
    ) -> int:
        custom_fields = []
        if phone:
            custom_fields.append(
                {"field_code": "PHONE", "values": [{"value": phone, "enum_code": "WORK"}]}
            )
        if email:
            custom_fields.append(
                {"field_code": "EMAIL", "values": [{"value": email, "enum_code": "WORK"}]}
            )
        body = [{"name": name, "custom_fields_values": custom_fields or None}]
        async with await self._client() as client:
            resp = await client.post("/api/v4/contacts", json=body)
            _raise_for_status(resp)
            return resp.json()["_embedded"]["contacts"][0]["id"]

    # ---------- Сделки ----------

    def _deal_custom_fields(
        self, *, source: str | None, amount: float | None, order_id: str | None
    ) -> list[dict]:
        fields = []
        if source and settings.amocrm_cf_source_id:
            fields.append(
                {"field_id": settings.amocrm_cf_source_id, "values": [{"value": source}]}
            )
        if amount is not None and settings.amocrm_cf_amount_id:
            fields.append(
                {"field_id": settings.amocrm_cf_amount_id, "values": [{"value": amount}]}
            )
        if order_id and settings.amocrm_cf_order_id:
            fields.append(
                {"field_id": settings.amocrm_cf_order_id, "values": [{"value": order_id}]}
            )
        if settings.amocrm_cf_source_select_id and settings.amocrm_cf_source_select_enum_id:
            fields.append(
                {
                    "field_id": settings.amocrm_cf_source_select_id,
                    "values": [{"enum_id": settings.amocrm_cf_source_select_enum_id}],
                }
            )
        return fields

    @_retry
    async def create_lead(
        self,
        *,
        name: str,
        contact_id: int,
        status_id: int | None,
        price: float | None = None,
        source: str | None = None,
        order_id: str | None = None,
    ) -> int:
        lead: dict = {
            "name": name,
            "_embedded": {"contacts": [{"id": contact_id}]},
        }
        if settings.amocrm_pipeline_id:
            lead["pipeline_id"] = settings.amocrm_pipeline_id
        if status_id:
            lead["status_id"] = status_id
        if price is not None:
            lead["price"] = int(price)
        cf = self._deal_custom_fields(source=source, amount=price, order_id=order_id)
        if cf:
            lead["custom_fields_values"] = cf

        async with await self._client() as client:
            resp = await client.post("/api/v4/leads", json=[lead])
            _raise_for_status(resp)
            return resp.json()["_embedded"]["leads"][0]["id"]

    @_retry
    async def update_lead_status(self, lead_id: int, status_id: int) -> None:
        async with await self._client() as client:
            resp = await client.patch(
                f"/api/v4/leads/{lead_id}", json={"status_id": status_id}
            )
            _raise_for_status(resp)

    @_retry
    async def add_note(self, lead_id: int, text: str) -> None:
        """Добавить служебное примечание (common) к сделке."""
        body = [{"note_type": "common", "params": {"text": text}}]
        async with await self._client() as client:
            resp = await client.post(f"/api/v4/leads/{lead_id}/notes", json=body)
            _raise_for_status(resp)
