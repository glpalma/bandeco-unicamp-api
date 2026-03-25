from zoneinfo import ZoneInfo
from pydantic_settings import BaseSettings, SettingsConfigDict

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Base URL — date is appended as ?d=YYYY-MM-DD
    cardapio_url: str = "https://sistemas.prefeitura.unicamp.br/apps/cardapio/index.php"
    database_url: str = "sqlite:///./bandeco.db"

    # Hour (24h, local time) at which the daily scraping job runs
    scrape_hour: int = 12
    scrape_minute: int = 0

    # Timeout in seconds for each HTTP request
    scrape_timeout_s: int = 15

    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
