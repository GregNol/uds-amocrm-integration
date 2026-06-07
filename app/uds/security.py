"""Проверка подписи вебхуков UDS (заголовок X-Signature).

UDS подписывает каждый вебхук. Точная схема подписи берётся из документации
UDS по вашему вебхуку. Здесь реализован распространённый вариант:

    X-Signature = base64( HMAC_SHA256(signing_key, X-Origin-Request-Id
                                                   + X-Timestamp + raw_body) )

Если AMOCRM/UDS используют другую конкатенацию — поправим в _build_message().
Проверка включается флагом UDS_VERIFY_SIGNATURE и наличием ключа
UDS_WEBHOOK_SIGNING_KEY. Пока выключено — вебхуки принимаются без проверки
(подпись только логируется), чтобы не блокировать первичную настройку.
"""
import base64
import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def _build_message(request_id: str, timestamp: str, raw_body: bytes) -> bytes:
    return f"{request_id}{timestamp}".encode() + raw_body


def verify_signature(
    *, request_id: str | None, timestamp: str | None, signature: str | None, raw_body: bytes
) -> bool:
    """True, если подпись валидна или проверка отключена."""
    if not settings.uds_verify_signature or not settings.uds_webhook_signing_key:
        if signature:
            logger.debug("X-Signature получен, проверка отключена: %s", signature)
        return True

    if not (request_id and timestamp and signature):
        logger.warning("Нет обязательных заголовков подписи UDS")
        return False

    message = _build_message(request_id, timestamp, raw_body)
    digest = hmac.new(
        settings.uds_webhook_signing_key.encode(), message, hashlib.sha256
    ).digest()
    expected = base64.b64encode(digest).decode()
    ok = hmac.compare_digest(expected, signature)
    if not ok:
        logger.warning("Подпись UDS не совпала (ожид. %s, пришла %s)", expected, signature)
    return ok
