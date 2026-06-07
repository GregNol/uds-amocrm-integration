from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # amoCRM
    amocrm_subdomain: str
    amocrm_client_id: str = ""
    amocrm_client_secret: str = ""
    amocrm_redirect_uri: str = ""
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
