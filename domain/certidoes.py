"""Modelo e extrator das certidões obrigatórias."""

from __future__ import annotations
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel
from .base import StatusCertidao


class CertidaoExtraida(BaseModel):
    tipo: str
    status: StatusCertidao = StatusCertidao.AUSENTE
    data_validade: Optional[date] = None


class CertidoesExtraidas(BaseModel):
    federal_divida_ativa: CertidaoExtraida = CertidaoExtraida(tipo="Federal + Dívida Ativa")
    estadual: CertidaoExtraida                = CertidaoExtraida(tipo="Estadual")
    municipal: CertidaoExtraida               = CertidaoExtraida(tipo="Municipal")
    cndt: CertidaoExtraida                    = CertidaoExtraida(tipo="CNDT")
    fgts_crf: CertidaoExtraida               = CertidaoExtraida(tipo="FGTS – CRF")


def _parse_status(texto: str) -> StatusCertidao:
    t = texto.lower()
    if "positiva com efeito" in t or "positiva c/ efeito" in t:
        return StatusCertidao.POSITIVA_EFEITO_NEGATIVA
    if "negativa" in t:
        return StatusCertidao.NEGATIVA
    if "positiva" in t:
        return StatusCertidao.POSITIVA
    # CRF/FGTS usa "REGULAR"/"IRREGULAR" em vez de "NEGATIVA"/"POSITIVA".
    # "regularidade" aparece no próprio título ("Certificado de Regularidade do FGTS").
    if re.search(r"\birregular\b", t):
        return StatusCertidao.POSITIVA
    if re.search(r"\bregular(idade)?\b", t):
        return StatusCertidao.NEGATIVA
    return StatusCertidao.AUSENTE


def _parse_validade(texto: str) -> Optional[date]:
    # Formato "válida até DD/MM/YYYY" ou "válido até DD/MM/YYYY"
    m = re.search(r"v[aá]lida?\s+at[eé]\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    if m:
        try:
            d, me, a = m.group(1).split("/")
            return date(int(a), int(me), int(d))
        except Exception:
            pass

    # Formato FGTS: "Validade: DD/MM/YYYY a DD/MM/YYYY" — captura a data FINAL (intervalo)
    # Deve ser testado ANTES do padrão simples "validade: data"
    m = re.search(
        r"validade\s*[:\-]?\s*\d{2}/\d{2}/\d{4}\s+a\s+(\d{2}/\d{2}/\d{4})",
        texto, re.IGNORECASE,
    )
    if m:
        try:
            d, me, a = m.group(1).split("/")
            return date(int(a), int(me), int(d))
        except Exception:
            pass

    # Formato "validade: DD/MM/YYYY" (CNDT e outros)
    m = re.search(r"validade\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    if m:
        try:
            d, me, a = m.group(1).split("/")
            return date(int(a), int(me), int(d))
        except Exception:
            pass

    # Formato Estadual BA: "válida por N dias, contados a partir de DD/MM/YYYY"
    # ou "emitida em DD/MM/YYYY" + "válida por N dias"
    m_dias = re.search(r"v[aá]lida?\s+por\s+(\d+)\s+dias?", texto, re.IGNORECASE)
    if m_dias:
        n_dias = int(m_dias.group(1))
        # Procura data de emissão no mesmo bloco
        m_emissao = re.search(
            r"(?:emiss[aã]o|emitida?\s+em|data\s+de\s+emiss[aã]o)\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
            texto, re.IGNORECASE,
        )
        if not m_emissao:
            # Fallback: primeira data no documento pode ser a de emissão
            m_emissao = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
        if m_emissao:
            try:
                from datetime import timedelta
                d, me, a = m_emissao.group(1).split("/")
                data_emissao = date(int(a), int(me), int(d))
                return data_emissao + timedelta(days=n_dias)
            except Exception:
                pass

    return None


# Âncoras únicas de cada tipo de certidão (usadas tanto para localização quanto
# para delimitar seções quando várias certidões estão num único bloco de texto).
_ANC_FEDERAL  = [r"certid[aã]o\s+conjunta", r"receita\s+federal", r"pgfn", r"rfb",
                 r"d[ií]vida\s+ativa\s+da\s+uni[aã]o", r"fazenda\s+nacional"]
_ANC_ESTADUAL = [r"secretaria\s+(?:de\s+estado\s+)?da\s+fazenda",
                 r"fazenda\s+p[úu]blica\s+do\s+estado",
                 r"sefaz\b", r"governo\s+do\s+estado"]
_ANC_MUNI     = [r"prefeitura", r"certid[aã]o\s+municipal", r"issqn",
                 r"fazenda\s+municipal", r"tributos\s+municipais"]
_ANC_CNDT     = [r"\bcndt\b", r"d[eé]bitos\s+trabalhistas", r"tst\.jus\.br",
                 r"certid[aã]o\s+(?:negativa\s+)?de\s+d[eé]bitos\s+trabalhistas"]
_ANC_FGTS     = [r"\bfgts\b", r"\bcrf\b", r"certificado\s+de\s+regularidade",
                 r"caixa\s+econ[oô]mica"]

_TODAS_ANCORAS = _ANC_FEDERAL + _ANC_ESTADUAL + _ANC_MUNI + _ANC_CNDT + _ANC_FGTS


def _primeira_pos(texto: str, anchors: list[str]) -> int:
    """Retorna a posição do início da linha onde aparece a primeira âncora, ou -1."""
    for anchor in anchors:
        m = re.search(anchor, texto, re.IGNORECASE)
        if m:
            ini = texto.rfind("\n", 0, m.start())
            return ini + 1 if ini >= 0 else 0
    return -1


def _secao_certidao(texto: str, anchors: list[str]) -> str:
    """Retorna a seção do bloco de texto correspondente a uma certidão específica.

    Delimita a seção entre a posição do anchor desta certidão e a posição do
    próximo anchor de QUALQUER outra certidão, eliminando contaminação cruzada.
    """
    inicio = _primeira_pos(texto, anchors)
    if inicio < 0:
        return ""

    # Encontra o próximo anchor de qualquer outra certidão após 'inicio'
    outros = [a for a in _TODAS_ANCORAS if a not in anchors]
    fim = len(texto)
    for outro in outros:
        m = re.search(outro, texto[inicio + 5:], re.IGNORECASE)  # +5 para não re-casar no próprio início
        if m:
            pos = inicio + 5 + m.start()
            # Recua até o início da linha
            ini_linha = texto.rfind("\n", 0, pos)
            pos_linha = ini_linha + 1 if ini_linha >= 0 else pos
            if pos_linha > inicio:
                fim = min(fim, pos_linha)

    return texto[inicio:fim]


def extrair_certidoes(texto: str) -> CertidoesExtraidas:
    """Tenta inferir status e validade de cada certidão a partir do texto do bloco.

    Quando o bloco contém múltiplas certidões (caso comum num único segmento PDF),
    cada tipo é analisado na sua própria sub-seção para evitar que a data de uma
    certidão seja atribuída a todas as outras.
    """
    def _extrair(anchors: list[str], tipo: str) -> CertidaoExtraida:
        sec = _secao_certidao(texto, anchors)
        if not sec:
            return CertidaoExtraida(tipo=tipo)
        return CertidaoExtraida(
            tipo=tipo,
            status=_parse_status(sec),
            data_validade=_parse_validade(sec),
        )

    return CertidoesExtraidas(
        federal_divida_ativa=_extrair(_ANC_FEDERAL,  "Federal + Dívida Ativa"),
        estadual=_extrair(_ANC_ESTADUAL, "Estadual"),
        municipal=_extrair(_ANC_MUNI,    "Municipal"),
        cndt=_extrair(_ANC_CNDT,         "CNDT"),
        fgts_crf=_extrair(_ANC_FGTS,     "FGTS – CRF"),
    )
