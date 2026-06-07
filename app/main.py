import json
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

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

@app.get("/uds/events")
async def uds_events(
    secret: str | None = None,
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
):
    """Отладка: последние пойманные события (сырой payload). Под тем же секретом."""
    if settings.uds_webhook_secret and secret != settings.uds_webhook_secret:
        raise HTTPException(status_code=403, detail="Bad secret")
    rows = (
        await session.execute(
            select(EventLog).order_by(EventLog.id.desc()).limit(min(limit, 100))
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "event_id": r.event_id,
            "event_type": r.event_type,
            "processed": r.processed,
            "error": r.error,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "payload": json.loads(r.payload),
        }
        for r in rows
    ]


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
    payload_json = json.dumps(payload, ensure_ascii=False)
    event = parse_webhook(payload)

    # Нераспознанный формат: всё равно сохраняем сырой payload для отладки парсера.
    if event is None:
        session.add(
            EventLog(
                event_id=f"raw:{uuid4()}",
                event_type="unknown",
                payload=payload_json,
                processed=True,
                error="не распознан parse_webhook",
            )
        )
        await session.commit()
        logger.info("UDS вебхук не распознан, сохранён в event_log как unknown")
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
        payload=payload_json,
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
