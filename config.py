"""Configuração centralizada – carregada de variáveis de ambiente ou .env"""

from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Power Automate – fluxo externo que recebe o PDF e devolve o relatório de saneamento
    # (extração, identificação de documentos, prompts e análise por IA acontecem todos lá)
    power_automate_processo_url: Optional[str] = None

    # Comportamento do serviço
    max_pdf_size_mb: int = 50
    log_level: str = "INFO"


settings = Settings()
