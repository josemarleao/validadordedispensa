"""Integração com Azure Blob Storage – preparado para produção."""

from __future__ import annotations
import logging
from typing import Optional
from config import settings

log = logging.getLogger(__name__)


def fazer_upload_blob(dados: bytes, nome_blob: str) -> Optional[str]:
    """Faz upload de bytes para o Azure Blob Storage.
    Retorna a URL pública do blob ou None se armazenamento não estiver configurado.
    """
    if not settings.azure_storage_enabled:
        log.debug("Azure Storage não configurado – blob não será armazenado.")
        return None

    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings

        cliente = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        container = cliente.get_container_client(settings.azure_storage_container)

        # Cria o container se não existir
        try:
            container.create_container()
        except Exception:
            pass  # já existe

        blob_client = container.get_blob_client(nome_blob)
        blob_client.upload_blob(
            dados,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/pdf"),
        )
        url = blob_client.url
        log.info("Blob '%s' armazenado em: %s", nome_blob, url)
        return url
    except ImportError:
        log.warning("azure-storage-blob não instalado. Blob não armazenado.")
        return None
    except Exception as exc:
        log.error("Falha no upload para Azure Blob: %s", exc)
        return None
