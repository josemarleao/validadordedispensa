"""Base do motor de regras normativas."""

from __future__ import annotations
import unicodedata
from abc import ABC, abstractmethod
from schemas.responses import ResultadoItem, StatusRegra, Providencia


def normalizar_rotulo_regra(s: str) -> str:
    """Normaliza rótulos de itens (determinístico × resposta da IA).

    Unifica espaços, NFKC e variantes de hífen/travessão para reduzir
    falhas de casamento quando o modelo devolve ``-`` em vez de ``–``.
    """
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s.strip())
    for ch in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212", "-"):
        t = t.replace(ch, "\u2013")
    return " ".join(t.split())


class Regra(ABC):
    """Unidade mínima de validação normativa."""

    @abstractmethod
    def aplicar(self, processo) -> list[ResultadoItem]:
        ...


def ok(documento: str, item: str, descricao: str) -> ResultadoItem:
    return ResultadoItem(
        documento=documento,
        item=item,
        status=StatusRegra.CONFORME,
        descricao=descricao,
        providencia=Providencia.PROSSEGUIR,
    )


def inconforme(
    documento: str,
    item: str,
    descricao: str,
    providencia: Providencia = Providencia.CORRIGIR,
) -> ResultadoItem:
    return ResultadoItem(
        documento=documento,
        item=item,
        status=StatusRegra.INCONFORME,
        descricao=descricao,
        providencia=providencia,
    )


def pendencia(
    documento: str,
    item: str,
    descricao: str,
    providencia: Providencia = Providencia.CORRIGIR,
) -> ResultadoItem:
    return ResultadoItem(
        documento=documento,
        item=item,
        status=StatusRegra.PENDENCIA,
        descricao=descricao,
        providencia=providencia,
    )
