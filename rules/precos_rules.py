"""Regras normativas da Tabela de Preços Orçados.

Fundamento: Modelo Tabela de Preços Orçados MPBA
            + art. 75, §3º, Lei 14.133/2021
            + Ato Normativo MPBA nº 048/2024.
Referência: knowledge_base.normas.ESTRUTURA_TABELA_PRECOS
            knowledge_base.normas.REGRAS_ORCAMENTOS
            knowledge_base.normas.REGRAS_AVISO_PREVIO
"""

from __future__ import annotations
from datetime import date
from domain.processo import ProcessoExtraido
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme, pendencia
from knowledge_base.normas import (
    ESTRUTURA_TABELA_PRECOS,
    REGRAS_ORCAMENTOS,
    REGRAS_AVISO_PREVIO,
)

_DOC = "Tabela de Preços Orçados"
_MIN_ORCAMENTOS = REGRAS_ORCAMENTOS["minimo_orcamentos"]             # 3
_MIN_AVISO_DU   = REGRAS_AVISO_PREVIO["prazo_minimo_dias_uteis"]     # 3


def aplicar_regras_precos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tp = processo.tabela_precos
    if tp is None:
        return [inconforme(_DOC, "Presença", "Tabela de Preços não localizada.", Providencia.CORRIGIR)]

    r: list[ResultadoItem] = []

    # Data
    if tp.data_orcamento is None:
        r.append(inconforme(_DOC, "Data do Orçamento", "Data não identificada."))
    elif tp.data_orcamento > date.today():
        r.append(inconforme(_DOC, "Data do Orçamento", f"Data futura proibida: {tp.data_orcamento}."))
    else:
        r.append(ok(_DOC, "Data do Orçamento", f"{tp.data_orcamento}"))

    # Aviso prévio publicado (art. 75, §3º, Lei 14.133/2021)
    if tp.aviso_previo_publicado is None:
        r.append(inconforme(
            _DOC, "Aviso Prévio",
            "Campo 'Aviso prévio publicado no sítio eletrônico' não identificado na Tabela. "
            "Obrigatório conforme art. 75, §3º, Lei 14.133/2021.",
        ))
    elif tp.aviso_previo_publicado == "NÃO":
        r.append(inconforme(
            _DOC, "Aviso Prévio",
            "Aviso prévio NÃO publicado. Verificar justificativa de urgência ou "
            f"providenciar publicação com antecedência mínima de {_MIN_AVISO_DU} dias úteis "
            "(art. 75, §3º, Lei 14.133/2021).",
        ))
    else:
        r.append(ok(_DOC, "Aviso Prévio", f"Publicado ✓ ({REGRAS_AVISO_PREVIO['veiculo']})"))

    # Propostas recebidas
    if tp.propostas_recebidas == "NÃO":
        r.append(inconforme(
            _DOC, "Propostas Recebidas",
            "Nenhuma proposta recebida após publicação do aviso. "
            "Documentar tentativas frustradas e obter ao menos 1 proposta.",
        ))

    # Quantidade de orçamentos (mínimo 3 conforme art. 75, §3º e IN SEGES)
    total = tp.total_orcamentos or len(processo.orcamentos)
    if total < _MIN_ORCAMENTOS:
        if not tp.justificativa_poucos_orcamentos:
            r.append(inconforme(
                _DOC, "Quantidade de Orçamentos",
                f"Apenas {total} orçamento(s) – mínimo exigido: {_MIN_ORCAMENTOS}. "
                "Apresentar justificativa formal para o número inferior.",
            ))
        else:
            r.append(ok(
                _DOC, "Quantidade de Orçamentos",
                f"{total} orçamento(s) com justificativa ✓",
            ))

    # Metodologia
    if not tp.metodologia_menor_preco:
        r.append(inconforme(_DOC, "Metodologia", "Metodologia 'menor preço' não identificada."))
    else:
        r.append(ok(_DOC, "Metodologia", "Menor preço ✓"))

    
    # Motivação fornecedores
    if not tp.motivacao_fornecedores:
        r.append(inconforme(_DOC, "Motivação Fornecedores", "Motivação para escolha dos fornecedores ausente."))

    # Responsável
    if not tp.responsavel_nome:
        r.append(inconforme(_DOC, "Responsável pela Pesquisa", "Nome do responsável não identificado."))

    # Coerência com gestor
    if tp.valor_global and processo.gestor and processo.gestor.valor_global:
        diff = abs(tp.valor_global - processo.gestor.valor_global)
        if diff > 0.01:
            r.append(inconforme(
                _DOC, "Coerência Tabela × Gestor",
                f"Valor global tabela R$ {tp.valor_global:,.2f} ≠ gestor R$ {processo.gestor.valor_global:,.2f}.",
            ))

    return r
