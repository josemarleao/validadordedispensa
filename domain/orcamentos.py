"""Modelo e extrator dos Orçamentos/Propostas."""

from __future__ import annotations
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel
from .base import limpar_cnpj, validar_cnpj


class OrcamentoExtraido(BaseModel):
    razao_social: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    cnpj_valido: bool = False
    endereco: Optional[str] = None
    objeto: Optional[str] = None
    valor_total: Optional[float] = None
    data_proposta: Optional[date] = None
    prazo_execucao: Optional[str] = None
    validade_dias: Optional[int] = None
    tem_assinatura: bool = False
    email_origem: Optional[str] = None


def extrair_orcamento(texto: str) -> OrcamentoExtraido:
    def buscar(pattern: str) -> Optional[str]:
        m = re.search(pattern, texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    cnpj_raw = buscar(r"cnpj\s*[:\-]?\s*([\d.\/\-]+)")
    cnpj_valido = validar_cnpj(cnpj_raw or "")

    # Razão Social – remove artefatos OCR isolados no fim da linha (ex: "o", "x")
    razao_raw = buscar(r"raz[aã]o\s+social\s*[:\-]?\s*([^\n]+)")
    if razao_raw:
        razao_raw = re.sub(r"\s+[a-zA-Z]\s*$", "", razao_raw).strip()

    # Data: "Data: DD/MM/YYYY", "Data da proposta: DD/MM/YYYY" ou "Cidade, DD de mês de YYYY"
    data_prop = None
    _MESES = {"janeiro":1,"fevereiro":2,"março":3,"abril":4,"maio":5,"junho":6,
               "julho":7,"agosto":8,"setembro":9,"outubro":10,"novembro":11,"dezembro":12}
    m_d = re.search(
        r"data\s+(?:da\s+)?(?:proposta|cotac[aã]o)?\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})"
        r"|data\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})",
        texto, re.IGNORECASE,
    )
    if not m_d:
        # Formato "DD de mês de YYYY" (ex: Salvador, 15 de março de 2025)
        m_d = re.search(
            r"(\d{1,2})\s+de\s+([a-záéíóúç]+)\s+de\s+(\d{4})",
            texto, re.IGNORECASE,
        )
        if m_d:
            try:
                dia, mes_str, ano = int(m_d.group(1)), m_d.group(2).lower(), int(m_d.group(3))
                mes = _MESES.get(mes_str)
                if mes:
                    data_prop = date(ano, mes, dia)
            except Exception:
                pass
            m_d = None  # já processado
    if m_d:
        raw = m_d.group(1) or m_d.group(2) or ""
        try:
            d, me, a = raw.split("/")
            data_prop = date(int(a), int(me), int(d))
        except Exception:
            pass

    # Valor: aceita "Valor Total", "Valor Global", "Total Geral" ou último R$ com decimal
    valor = None
    m_v = re.search(
        r"valor\s+(?:total|global|da\s+proposta|da\s+contrata[cç][aã]o)\s*[:\-]?\s*R?\$?\s*([\d.,]+)"
        r"|total\s+geral\s*[:\-]?\s*R?\$?\s*([\d.,]+)",
        texto, re.IGNORECASE,
    )
    if not m_v:
        # Último valor "R$ X.XXX,XX" no documento como fallback
        todos = re.findall(r"R\$\s*([\d.]+,\d{2})\b", texto, re.IGNORECASE)
        if todos:
            m_v = type("m", (), {"group": lambda self, n: todos[-1]})()  # mock simples
    if m_v:
        try:
            raw_v = m_v.group(1) or m_v.group(2) or ""
            if not raw_v and hasattr(m_v, "group"):
                raw_v = m_v.group(1) or ""
            valor = float(raw_v.replace(".", "").replace(",", "."))
        except (ValueError, AttributeError):
            pass

    validade = None
    m_val = re.search(r"validade\s*[:\-]?\s*(\d+)\s*dias?", texto, re.IGNORECASE)
    if m_val:
        validade = int(m_val.group(1))

    return OrcamentoExtraido(
        razao_social=razao_raw,
        cnpj_cpf=cnpj_raw,
        cnpj_valido=cnpj_valido,
        endereco=buscar(r"endere[cç]o\s*[:\-]?\s*([^\n]+)"),
        objeto=buscar(r"objeto\s*[:\-]?\s*([^\n]+)"),
        valor_total=valor,
        data_proposta=data_prop,
        prazo_execucao=buscar(r"prazo\s+de\s+execu[cç][aã]o\s*[:\-]?\s*([^\n]+)"),
        validade_dias=validade,
        tem_assinatura=bool(re.search(r"assina[dt]|rubrica", texto, re.IGNORECASE)),
        email_origem=buscar(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    )
