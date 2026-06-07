"""Вывести ID воронок, статусов и кастомных полей сделок amoCRM.

Запуск (после успешной OAuth-авторизации, токены уже в БД):
    docker compose exec app python -m scripts.dump_amocrm_meta

Скопируй нужные ID в .env (AMOCRM_PIPELINE_ID, *_STATUS_*, *_CF_*).
"""
import asyncio

import httpx

from app.amocrm.oauth import get_access_token
from app.config import settings
from app.db import SessionLocal


async def main() -> None:
    async with SessionLocal() as session:
        token = await get_access_token(session)

    async with httpx.AsyncClient(
        base_url=settings.amocrm_base_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    ) as client:
        print("\n=== ВОРОНКИ И СТАТУСЫ ===")
        resp = await client.get("/api/v4/leads/pipelines")
        resp.raise_for_status()
        for p in resp.json()["_embedded"]["pipelines"]:
            print(f"\nВоронка: {p['name']}  (pipeline_id={p['id']})")
            for s in p["_embedded"]["statuses"]:
                print(f"  статус: {s['name']:<30} status_id={s['id']}")

        print("\n=== КАСТОМНЫЕ ПОЛЯ СДЕЛОК ===")
        resp = await client.get("/api/v4/leads/custom_fields")
        resp.raise_for_status()
        for f in resp.json().get("_embedded", {}).get("custom_fields", []):
            print(f"  поле: {f['name']:<30} field_id={f['id']}  type={f['type']}")


if __name__ == "__main__":
    asyncio.run(main())
