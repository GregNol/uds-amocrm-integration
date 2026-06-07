"""OAuth 2.0 для amoCRM: обмен кода на токены и авто-рефреш.

Токены хранятся в таблице amocrm_tokens (одна строка, id=1).
access_token живёт 24 часа, refresh_token — 3 месяца и одноразовый
(каждый рефреш возвращает новую пару).
"""
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import TokenStore

_REFRESH_SKEW = timedelta(minutes=5)  # рефрешим заранее, не дожидаясь протухания


async def _save_tokens(session: AsyncSession, data: dict) -> TokenStore:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])
    token = await session.get(TokenStore, 1)
    if token is None:
        token = TokenStore(id=1)
        session.add(token)
    token.access_token = data["access_token"]
    token.refresh_token = data["refresh_token"]
    token.expires_at = expires_at
    await session.commit()
    await session.refresh(token)
    return token


async def exchange_code(session: AsyncSession, code: str) -> TokenStore:
    """Первичный обмен authorization_code на пару токенов."""
    payload = {
        "client_id": settings.amocrm_client_id,
        "client_secret": settings.amocrm_client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.amocrm_redirect_uri,
    }
    async with httpx.AsyncClient(base_url=settings.amocrm_base_url, timeout=30) as client:
        resp = await client.post("/oauth2/access_token", json=payload)
        resp.raise_for_status()
        return await _save_tokens(session, resp.json())


async def _refresh(session: AsyncSession, token: TokenStore) -> TokenStore:
    payload = {
        "client_id": settings.amocrm_client_id,
        "client_secret": settings.amocrm_client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token.refresh_token,
        "redirect_uri": settings.amocrm_redirect_uri,
    }
    async with httpx.AsyncClient(base_url=settings.amocrm_base_url, timeout=30) as client:
        resp = await client.post("/oauth2/access_token", json=payload)
        resp.raise_for_status()
        return await _save_tokens(session, resp.json())


async def get_access_token(session: AsyncSession) -> str:
    """Вернуть валидный access_token, при необходимости обновив его."""
    token = (await session.execute(select(TokenStore).limit(1))).scalar_one_or_none()
    if token is None:
        raise RuntimeError(
            "amoCRM не авторизован. Пройдите OAuth: GET /amocrm/auth"
        )
    if datetime.now(timezone.utc) >= token.expires_at - _REFRESH_SKEW:
        token = await _refresh(session, token)
    return token.access_token
