"""Regras normativas dos Orçamentos/Propostas.

Fundamento: art. 75, §3º, Lei 14.133/2021
            + Modelos de Proposta MPBA (Aquisições e Serviços)
            + Ato Normativo MPBA nº 048/2024.
Referência: knowledge_base.normas.REGRAS_ORCAMENTOS
            knowledge_base.normas.ESTRUTURA_PROPOSTA
            knowledge_base.normas.REGRAS_DOCUMENTO_BANCARIO
"""

from __future__ import annotations
from datetime import date, timedelta
from domain.processo import ProcessoExtraido
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme, pendencia
from knowledge_base.normas import REGRAS_ORCAMENTOS, ESTRUTURA_PROPOSTA, REGRAS_DOCUMENTO_BANCARIO

_DOC = "Orçamentos / Propostas"
_MIN_ORCAMENTOS = REGRAS_ORCAMENTOS["minimo_orcamentos"]        # 3
_VALIDADE_PADRAO = ESTRUTURA_PROPOSTA["validade_padrao_dias"]    # 180


def aplicar_regras_orcamentos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    if not processo.orcamentos:
        return [inconforme(_DOC, "Presença", "Nenhum orçamento localizado no processo.", Providencia.CORRIGIR)]

    r: list[ResultadoItem] = []
    hoje = date.today()

    # Quantidade mínima de orçamentos (art. 75, §3º, Lei 14.133/2021)
    total = len(processo.orcamentos)
    if total < _MIN_ORCAMENTOS:
        r.append(inconforme(
            _DOC, "Quantidade Mínima",
            f"{total} orçamento(s) localizado(s). Mínimo exigido: {_MIN_ORCAMENTOS} "
            f"({REGRAS_ORCAMENTOS['norma']}). "
            "Apresentar os demais orçamentos ou justificativa formal.",
        ))
    else:
        r.append(ok(_DOC, "Quantidade Mínima", f"{total} orçamentos ✓ (mínimo: {_MIN_ORCAMENTOS})"))

    # Individual field validations removed as requested

    return r
