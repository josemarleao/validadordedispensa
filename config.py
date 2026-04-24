"""Configuração centralizada – carregada de variáveis de ambiente ou .env"""

from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Azure Storage
    azure_storage_connection_string: Optional[str] = None
    azure_storage_container: str = "processos-dl"

    # Azure Document Intelligence (OCR avançado)
    azure_doc_intelligence_endpoint: Optional[str] = None
    azure_doc_intelligence_key: Optional[str] = None

    # Google AI (Gemini API) – análise subsidiária por IA (modelos Gemini ou Gemma)
    gemini_api_key: Optional[str] = None
    ia_enabled: bool = False
    
    # OpenRouter – alternativa gratuita para IA (modelos free) - PADRÃO
    openrouter_api_key: Optional[str] = None
    ia_provider: str = "openrouter"  # "gemini" ou "openrouter"
    ia_model: str = "openrouter/free"  # Modelo padrão OpenRouter free

    # Comportamento do serviço
    max_pdf_size_mb: int = 50
    ocr_enabled: bool = True
    log_level: str = "INFO"

    @property
    def azure_storage_enabled(self) -> bool:
        return bool(self.azure_storage_connection_string)

    @property
    def azure_doc_intelligence_enabled(self) -> bool:
        return bool(self.azure_doc_intelligence_endpoint and self.azure_doc_intelligence_key)


settings = Settings()
