"""Tipos base compartilhados entre todos os modelos de domínio."""

from __future__ import annotations
import re
import unicodedata
from enum import Enum
from typing import Optional
from datetime import date


class StatusCertidao(str, Enum):
    NEGATIVA                  = "NEGATIVA"
    POSITIVA_EFEITO_NEGATIVA  = "POSITIVA_COM_EFEITO_NEGATIVA"
    POSITIVA                  = "POSITIVA"
    AUSENTE                   = "AUSENTE"


def normalizar(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sem_acento.lower()).strip()


def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)


def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]

    def dig(nums: str, pesos: list[int]) -> int:
        r = sum(int(d) * p for d, p in zip(nums, pesos)) % 11
        return 0 if r < 2 else 11 - r

    return cnpj[-2:] == f"{dig(cnpj[:12], pesos1)}{dig(cnpj[:13], pesos2)}"
