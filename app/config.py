from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator(
        "amocrm_pipeline_id",
        "amocrm_status_new_id",
        "amocrm_status_won_id",
        "amocrm_cf_source_id",
        "amocrm_cf_amount_id",
        "amocrm_cf_order_id",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, v):
        """Пустое значение в .env (например AMOCRM_CF_AMOUNT_ID=) трактуем как None."""
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    # amoCRM
    amocrm_subdomain: str
    amocrm_client_id: str = ""
    amocrm_client_secret: str = ""
    amocrm_redirect_uri: str = ""
    # Долгосрочный токен. Если задан — используется напрямую, OAuth не нужен.
    amocrm_long_lived_token: str = ""
    amocrm_pipeline_id: int | None = None
    amocrm_status_new_id: int | None = None
    amocrm_status_won_id: int | None = None
    amocrm_cf_source_id: int | None = None
    amocrm_cf_amount_id: int | None = None
    amocrm_cf_order_id: int | None = None

    # UDS
    uds_company_id: str = ""
    uds_api_key: str = ""
    uds_webhook_secret: str = ""
    # Проверка подписи вебхуков UDS (X-Signature). Ключ берётся из настроек
    # вебхука в кабинете UDS. Пока ключа нет — verify выключен (только лог).
    uds_webhook_signing_key: str = ""
    uds_verify_signature: bool = False

    # Infra
    database_url: str
    log_level: str = "INFO"

    @property
    def amocrm_base_url(self) -> str:
        return f"https://{self.amocrm_subdomain}.amocrm.ru"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
