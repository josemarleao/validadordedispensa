"""Modelo e extrator da Tabela de Preços Orçados."""

from __future__ import annotations
import re
from typing import Optional
from datetime import date
from pydantic import BaseModel


class ItemTabelaExtraido(BaseModel):
    item: Optional[str] = None
    descricao: Optional[str] = None
    quantidade: Optional[float] = None
    fornecedor_vencedor: Optional[str] = None
    cnpj_cpf: Optional[str] = None
    valor_unitario: Optional[float] = None
    valor_total: Optional[float] = None


class TabelaPrecosExtraida(BaseModel):
    """Tabela de Preços Orçados conforme modelo oficial MPBA."""
    itens: list[ItemTabelaExtraido] = []
    valor_global: Optional[float] = None
    total_orcamentos: Optional[int] = None
    metodologia_menor_preco: bool = False
    motivacao_fornecedores: Optional[str] = None
    data_orcamento: Optional[date] = None
    responsavel_matricula: Optional[str] = None
    responsavel_nome: Optional[str] = None
    responsavel_assinatura: Optional[str] = None
    justificativa_poucos_orcamentos: Optional[str] = None
    # Campos do cabeçalho do modelo MPBA (art. 75, §3º, Lei 14.133/2021)
    aviso_previo_publicado: Optional[str] = None    # "SIM" | "NÃO"
    propostas_recebidas: Optional[str] = None       # "SIM" | "NÃO"
    data_publicacao_aviso: Optional[date] = None
    blocos_texto: list[str] = []


def _parse_valor(texto: str) -> Optional[float]:
    m = re.search(r"R\$?\s*([\d.,]+)", texto)
    if not m:
        return None
    val = m.group(1).replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def extrair_tabela_precos(texto: str, blocos_texto: Optional[list[str]] = None) -> TabelaPrecosExtraida:
    t = texto

    # Valor global – "valor global" ou "valor total" (variante comum), multi-linha
    valor_global = _parse_valor(
        next(iter(re.findall(
            r"valor\s+(?:global|total)\s+(?:da\s+contrata[cç][aã]o\s*)?[\s\S]{0,80}?R\$\s*[\d.,]+",
            t, re.IGNORECASE,
        )), "")
    )
    if not valor_global:
        # Fallback: "valor total: R$ X" ou "valor global: R$ X" na mesma linha
        m_vg = re.search(
            r"valor\s+(?:global|total)\s*[:\-]?\s*R?\$?\s*([\d.,]+)",
            t, re.IGNORECASE,
        )
        if m_vg:
            try:
                valor_global = float(m_vg.group(1).replace(".", "").replace(",", "."))
            except ValueError:
                pass
    if not valor_global:
        # Último recurso: última ocorrência de "total" + valor numérico
        totais = re.findall(r"total\s*[:\-]?\s*R?\$?\s*([\d.,]+)", t, re.IGNORECASE)
        if totais:
            try:
                valor_global = float(totais[-1].replace(".", "").replace(",", "."))
            except ValueError:
                pass

    data_orc = None
    # Padrão específico para o modelo MPBA: "DATA DO ORÇAMENTO ESTIMADO PELA ADMINISTRAÇÃO: DD/MM/YYYY"
    m_data = re.search(
        r"data\s+do\s+or[cç]amento[^\n]{0,60}?(\d{2}/\d{2}/\d{4})"
        r"|data\s+do\s+or[cç]amento\s*[:\-]\s*(\d{2}/\d{2}/\d{4})"
        r"|data\s*[:\-]\s*(\d{2}/\d{2}/\d{4})",
        t, re.IGNORECASE,
    )
    if m_data:
        raw = m_data.group(1) or m_data.group(2) or m_data.group(3)
        try:
            d, me, a = raw.split("/")
            data_orc = date(int(a), int(me), int(d))
        except Exception:
            pass

    n_orc = None
    m_norc = re.search(r"(\d+)\s+orca[mn]entos?", t, re.IGNORECASE)
    if not m_norc:
        m_norc = re.search(r"(\d+)\s+(?:fornecedores?\s+consultados?|cota[çc][oõ]es?)", t, re.IGNORECASE)
    if m_norc:
        n_orc = int(m_norc.group(1))

    responsavel_nome = None
    m_resp = re.search(r"respons[aá]vel\s+pela\s+pesquisa\s*[:\-]?\s*([^\n]+)", t, re.IGNORECASE)
    if m_resp:
        responsavel_nome = m_resp.group(1).strip()

    # Aviso prévio publicado (cabeçalho do modelo MPBA)
    # O checkbox/resposta pode estar na linha seguinte ao rótulo
    aviso_previo = None
    _AVISO_BLOCO = re.search(
        r"aviso\s+pr[eé]vio\s+publicado[\s\S]{0,120}", t, re.IGNORECASE
    )
    if _AVISO_BLOCO:
        _ab = _AVISO_BLOCO.group(0)
        if re.search(r"\bsim\b", _ab, re.IGNORECASE):
            aviso_previo = "SIM"
        elif re.search(r"\bn[aã]o\b", _ab, re.IGNORECASE):
            aviso_previo = "NÃO"

    propostas_rec = None
    _PROP_BLOCO = re.search(
        r"propostas\s+recebidas[\s\S]{0,120}", t, re.IGNORECASE
    )
    if _PROP_BLOCO:
        _pb = _PROP_BLOCO.group(0)
        if re.search(r"\bsim\b", _pb, re.IGNORECASE):
            propostas_rec = "SIM"
        elif re.search(r"\bn[aã]o\b", _pb, re.IGNORECASE):
            propostas_rec = "NÃO"

    motivacao = None
    m_mot = re.search(
        r"(?:motiva[cç][aã]o|justificativa)\s+para\s+a?\s*escolha\s+dos\s+fornecedores"
        r"\s*[:\-]?\s*([^\n]+)",
        t, re.IGNORECASE,
    )
    if m_mot:
        motivacao = m_mot.group(1).strip()
    if not motivacao:
        # Conteúdo da seção: linha(s) após o cabeçalho
        m_mot2 = re.search(
            r"(?:motiva[cç][aã]o|justificativa)\s+para\s+a?\s*escolha\s+dos\s+fornecedores"
            r"[^\n]*\n\s*([^\n]{10,})",
            t, re.IGNORECASE,
        )
        if m_mot2:
            motivacao = m_mot2.group(1).strip()

    return TabelaPrecosExtraida(
        valor_global=valor_global,
        data_orcamento=data_orc,
        total_orcamentos=n_orc,
        metodologia_menor_preco=bool(re.search(r"menor\s+pre[cç]o", t, re.IGNORECASE)),
        responsavel_nome=responsavel_nome,
        aviso_previo_publicado=aviso_previo,
        propostas_recebidas=propostas_rec,
        motivacao_fornecedores=motivacao,
        blocos_texto=blocos_texto or [texto],
    )
