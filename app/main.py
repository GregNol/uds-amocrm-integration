import json
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.amocrm import oauth
from app.config import settings
from app.db import get_session, init_db
from app.models import EventLog
from app.services.sync import process_event
from app.uds.webhook import parse_webhook

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="UDS ↔ amoCRM integration", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------- amoCRM OAuth ----------

@app.get("/amocrm/auth")
async def amocrm_auth():
    """Редирект на страницу выдачи прав amoCRM (удобно для первичной авторизации)."""
    url = (
        f"{settings.amocrm_base_url}/oauth"
        f"?client_id={settings.amocrm_client_id}"
        f"&mode=post_message"
    )
    return RedirectResponse(url)


@app.get("/amocrm/callback", response_class=HTMLResponse)
async def amocrm_callback(
    code: str | None = None,
    error: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """amoCRM возвращает сюда authorization_code — обмениваем на токены."""
    if error:
        raise HTTPException(status_code=400, detail=f"amoCRM error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Не передан code")
    await oauth.exchange_code(session, code)
    return "<h3>amoCRM авторизован. Токены сохранены. Можно закрыть окно.</h3>"


# ---------- UDS webhook ----------

@app.post("/uds/webhook")
async def uds_webhook(
    request: Request,
    secret: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    # Проверка секрета (UDS не подписывает вебхуки — защищаемся секретом в URL)
    if settings.uds_webhook_secret and secret != settings.uds_webhook_secret:
        raise HTTPException(status_code=403, detail="Bad secret")

    payload = await request.json()
    event = parse_webhook(payload)
    if event is None:
        return {"status": "ignored"}

    # Идемпотентность: повторный event_id не обрабатываем
    already = (
        await session.execute(
            select(EventLog).where(EventLog.event_id == event.event_id)
        )
    ).scalar_one_or_none()
    if already and already.processed:
        return {"status": "duplicate"}

    log = already or EventLog(
        event_id=event.event_id,
        event_type=event.event_type.value,
        payload=json.dumps(payload, ensure_ascii=False),
    )
    if already is None:
        session.add(log)
        await session.commit()

    try:
        await process_event(session, event)
        log.processed = True
        log.error = None
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Ошибка обработки события %s", event.event_id)
        log.error = str(exc)
        await session.commit()
        # 500 -> UDS повторит доставку
        raise HTTPException(status_code=500, detail="processing failed") from exc

    return {"status": "ok"}
