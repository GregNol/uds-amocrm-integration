import json
import logging
from collections.abc import Callable
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
from app.schemas import NormalizedEvent
from app.services.sync import process_event
from app.uds import client as uds_client
from app.uds.security import verify_signature
from app.uds.webhook import parse_operation, parse_order, parse_participant

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


async def _enrich_customer(event: NormalizedEvent) -> None:
    """Дотянуть из UDS API недостающее: телефон/email и канал-источник (channelName)."""
    need_contact = not (event.customer.phone or event.customer.email)
    need_channel = not event.customer.channel
    if not need_contact and not need_channel:
        return
    try:
        full = await uds_client.get_customer(event.customer.uds_customer_id)
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось обогатить клиента %s", event.customer.uds_customer_id)
        return
    if full:
        if need_contact:
            event.customer.phone = full.phone
            event.customer.email = full.email
        if need_channel:
            event.customer.channel = full.channel


async def _handle_webhook(
    request: Request,
    session: AsyncSession,
    parser: Callable[[dict, str], NormalizedEvent | None],
) -> dict:
    """Общий конвейер для всех вебхуков UDS."""
    raw_body = await request.body()
    # UDS называет заголовок по-разному в разных частях доки — читаем оба.
    header_request_id = request.headers.get("X-RequestId") or request.headers.get(
        "X-Origin-Request-Id"
    )

    if not verify_signature(
        request_id=header_request_id,
        timestamp=request.headers.get("X-Timestamp"),
        signature=request.headers.get("X-Signature"),
    ):
        raise HTTPException(status_code=403, detail="Bad signature")

    request_id = header_request_id or f"raw:{uuid4()}"
    payload = json.loads(raw_body or b"{}")
    payload_json = json.dumps(payload, ensure_ascii=False)
    event = parser(payload, request_id)

    # Событие пропущено парсером — сохраняем сырой payload для отладки.
    if event is None:
        session.add(
            EventLog(
                event_id=f"skip:{request_id}:{uuid4()}",
                event_type="skipped",
                payload=payload_json,
                processed=True,
            )
        )
        await session.commit()
        return {"status": "ignored"}

    # Идемпотентность по X-Origin-Request-Id
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
        await _enrich_customer(event)
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


@app.post("/api/v2/events/operation")
async def uds_operation(request: Request, session: AsyncSession = Depends(get_session)):
    return await _handle_webhook(request, session, parse_operation)


@app.post("/api/v2/events/participant")
async def uds_participant(request: Request, session: AsyncSession = Depends(get_session)):
    return await _handle_webhook(request, session, parse_participant)


@app.post("/api/v2/events/order")
async def uds_order(request: Request, session: AsyncSession = Depends(get_session)):
    return await _handle_webhook(request, session, parse_order)
