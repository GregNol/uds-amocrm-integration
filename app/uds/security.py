"""Проверка подписи вебхуков UDS (заголовок X-Signature).

UDS подписывает каждый вебхук:

    X-Signature = md5( X-RequestId + X-Timestamp + Client-Id + Api-Key )   (hex)

Тело запроса в подпись НЕ входит. Client-Id и Api-Key — это UDS_COMPANY_ID
и UDS_API_KEY. Заголовок request-id в разных частях доки UDS называется
по-разному (X-RequestId / X-Origin-Request-Id) — читаем оба варианта.
"""
import hashlib
import hmac
import logging

from app.config import settings

logger = logging.getLogger(__name__)


def verify_signature(
    *, request_id: str | None, timestamp: str | None, signature: str | None
) -> bool:
    """True, если подпись валидна или проверка отключена (UDS_VERIFY_SIGNATURE)."""
    if not settings.uds_verify_signature:
        return True

    if not (request_id and timestamp and signature):
        logger.warning("Нет обязательных заголовков подписи UDS")
        return False

    raw = f"{request_id}{timestamp}{settings.uds_company_id}{settings.uds_api_key}"
    expected = hashlib.md5(raw.encode()).hexdigest()
    ok = hmac.compare_digest(expected, signature.strip().lower())
    if not ok:
        logger.warning("Подпись UDS не совпала (ожид. %s, пришла %s)", expected, signature)
    return ok
