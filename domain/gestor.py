"""Modelo e extrator de manifestações do gestor e ciências."""

from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel


class GestorExtraido(BaseModel):
    objeto_descricao: Optional[str] = None
    codigo_pdm: Optional[str] = None
    valor_global: Optional[float] = None
    nome_executor: Optional[str] = None
    nome_gestor: Optional[str] = None
    nome_fiscal: Optional[str] = None
    executor_e_fiscal: bool = False
    assinou: bool = False


class CienciaExtraida(BaseModel):
    nome: Optional[str] = None
    funcao: Optional[str] = None
    assinou: bool = False


def extrair_gestor(texto: str) -> GestorExtraido:
    def buscar(pattern: str) -> Optional[str]:
        m = re.search(pattern, texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    v = None
    m_v = re.search(r"valor\s+global\s*[:\-]?\s*R?\$?\s*([\d.,]+)", texto, re.IGNORECASE)
    if m_v:
        try:
            v = float(m_v.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass

    executor = buscar(r"executor\s+or[cç]ament[aá]rio\s*[:\-]?\s*([^\n]+)")
    gestor   = buscar(r"gestor\s+do\s+contrato\s*[:\-]?\s*([^\n]+)")
    fiscal   = buscar(r"fiscal\s+do\s+contrato\s*[:\-]?\s*([^\n]+)")

    # Código PDM/CATMAT/Serviços — múltiplos formatos possíveis
    def _buscar_codigo(pattern: str) -> Optional[str]:
        m = re.search(pattern, texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    executor_e_fiscal = (
        executor is not None
        and fiscal is not None
        and executor.lower() == fiscal.lower()
    )

    codigo_pdm = (
        _buscar_codigo(r"pdm\s*[:\-]?\s*(\d[\d\s\-\.]+)")
        or _buscar_codigo(r"catmat\s*[:\-]?\s*(\d[\d\s\-\.]+)")
        or _buscar_codigo(r"catser\s*[:\-]?\s*(\d[\d\s\-\.]+)")
        or _buscar_codigo(r"c[oó]digo\s*(?:de\s+(?:material|servi[cç]o|produto))?\s*[:\-]\s*(\d[\d\s\-\.]+)")
        or _buscar_codigo(r"\b(\d{5,6})\s*[-–]\s*[A-ZÀ-Ú]")  # padrão "10832 – Placa de Identificação"
    )
    # Remove espaços internos e trata valor como código numérico limpo
    if codigo_pdm:
        codigo_pdm = re.sub(r"\s+", "", codigo_pdm).rstrip("-.")

    return GestorExtraido(
        objeto_descricao=buscar(r"objeto\s*[:\-]?\s*([^\n]+)"),
        codigo_pdm=codigo_pdm,
        valor_global=v,
        nome_executor=executor,
        nome_gestor=gestor,
        nome_fiscal=fiscal,
        executor_e_fiscal=executor_e_fiscal,
        assinou=bool(re.search(r"assina[dt]|rubrica", texto, re.IGNORECASE)),
    )


def extrair_ciencias(texto: str) -> list[CienciaExtraida]:
    """Extrai múltiplas manifestações de ciência de um bloco de texto."""
    ciencias: list[CienciaExtraida] = []
    blocos = re.split(r"(?i)ciente\s*[:\-]?|ci[eê]ncia\s*[:\-]?", texto)
    for bloco in blocos[1:]:  # primeiro bloco é antes do primeiro "ciente"
        nome_m = re.search(r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+)+)", bloco)
        funcao_m = re.search(r"(?:gestor|fiscal|executor)[^\n]*", bloco, re.IGNORECASE)
        assinou = bool(re.search(r"assina[dt]|rubrica", bloco, re.IGNORECASE))
        ciencias.append(CienciaExtraida(
            nome=nome_m.group(1) if nome_m else None,
            funcao=funcao_m.group(0).strip() if funcao_m else None,
            assinou=assinou,
        ))
    return ciencias or [CienciaExtraida()]
