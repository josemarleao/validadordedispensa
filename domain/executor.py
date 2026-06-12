"""Modelos e extratores dos documentos financeiros/orçamentários."""

from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel


class ExecutorExtraido(BaseModel):
    valor_global: Optional[float] = None
    natureza_despesa: Optional[str] = None
    percentual_dotacao: Optional[float] = None
    percentual_empenhado: Optional[float] = None
    linhas_preenchidas: bool = False


class MemoriaCalculoExtraida(BaseModel):
    limite_legal: Optional[float] = None
    valor_comprometido: Optional[float] = None
    saldo_positivo: bool = True


class FIPLANExtraido(BaseModel):
    ano: Optional[int] = None
    ug: Optional[str] = None
    natureza_despesa: Optional[str] = None
    valor_total: Optional[float] = None


def _parse_valor(texto: str) -> Optional[float]:
    m = re.search(r"R\$?\s*([\d.,]+)", texto)
    if not m:
        return None
    try:
        return float(m.group(1).replace(".", "").replace(",", "."))
    except ValueError:
        return None


_PLACEHOLDER = re.compile(r"^[\s*\-_./]+$")


def _limpar(valor: Optional[str]) -> Optional[str]:
    """Descarta valores que são apenas placeholders (**, --, etc.)."""
    if valor and not _PLACEHOLDER.match(valor.strip()):
        return valor.strip()
    return None


def extrair_executor(texto: str) -> ExecutorExtraido:
    nd = re.search(
        r"(?:natureza\s+da\s+despesa|destina[cç][aã]o\s+de\s+recursos"
        r"|elemento\s+de\s+despesa|classifica[cç][aã]o\s+or[cç]ament[aá]ria)"
        r"\s*[:\-]?\s*([^\n]+)",
        texto, re.IGNORECASE,
    )
    v = re.search(
        r"valor\s+(?:global|total)\s*[:\-]?\s*R?\$?\s*([\d.,]+)",
        texto, re.IGNORECASE,
    )
    valor = None
    if v:
        try:
            valor = float(v.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass
    return ExecutorExtraido(
        valor_global=valor,
        natureza_despesa=_limpar(nd.group(1)) if nd else None,
        linhas_preenchidas=bool(re.search(r"unidade\s+or[cç]ament[aá]ria", texto, re.IGNORECASE)),
    )


def extrair_memoria_calculo(texto: str) -> MemoriaCalculoExtraida:
    limite = _parse_valor(
        next(iter(re.findall(r"limite\s+legal.*?R\$\s*[\d.,]+", texto, re.IGNORECASE)), "")
    )
    comprometido = _parse_valor(
        next(iter(re.findall(r"comprometido.*?R\$\s*[\d.,]+", texto, re.IGNORECASE)), "")
    )
    saldo_positivo = True
    if limite is not None and comprometido is not None:
        saldo_positivo = (limite - comprometido) >= 0
    return MemoriaCalculoExtraida(
        limite_legal=limite,
        valor_comprometido=comprometido,
        saldo_positivo=saldo_positivo,
    )


def extrair_fiplan(texto: str) -> FIPLANExtraido:
    nd = re.search(r"natureza\s+da\s+despesa\s*[:\-]?\s*([^\n]+)", texto, re.IGNORECASE)
    ug = re.search(r"unidade\s+gestora\s*[:\-]?\s*([^\n]+)", texto, re.IGNORECASE)
    ano_m = re.search(r"\b(20\d{2})\b", texto)
    v = _parse_valor(
        next(iter(re.findall(r"valor\s+total.*?R\$\s*[\d.,]+", texto, re.IGNORECASE)), "")
    )
    return FIPLANExtraido(
        ano=int(ano_m.group(1)) if ano_m else None,
        ug=ug.group(1).strip() if ug else None,
        natureza_despesa=nd.group(1).strip() if nd else None,
        valor_total=v,
    )
