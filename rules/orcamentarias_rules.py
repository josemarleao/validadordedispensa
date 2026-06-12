"""Regras das peças orçamentárias: Executor, Memória, FIPLAN, Gestor, Ciências.

Fundamento: Ato Normativo MPBA nº 048/2024 + art. 117, Lei 14.133/2021.
Referência: knowledge_base.normas.REGRAS_GESTOR_FISCAL
"""

from __future__ import annotations
from domain.processo import ProcessoExtraido
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme, pendencia
from knowledge_base.normas import REGRAS_GESTOR_FISCAL, NORMAS_GERAIS

_TOLERANCIA = 0.01


def aplicar_regras_orcamentarias(processo: ProcessoExtraido) -> list[ResultadoItem]:
    r: list[ResultadoItem] = []
    r.extend(_executor(processo))
    r.extend(_memoria(processo))
    r.extend(_fiplan(processo))
    r.extend(_gestor(processo))
    r.extend(_ciencias(processo))
    return r


def _executor(processo: ProcessoExtraido) -> list[ResultadoItem]:
    ex = processo.executor
    if ex is None:
        return [inconforme("Executor Orçamentário", "Presença", "Documento não localizado.")]
    r = []
    if not ex.linhas_preenchidas:
        r.append(inconforme("Executor Orçamentário", "Item I – Tabela", "Colunas orçamentárias não identificadas."))
    if not ex.natureza_despesa:
        r.append(inconforme("Executor Orçamentário", "Natureza da Despesa", "Campo não identificado."))
    if ex.valor_global and processo.tabela_precos and processo.tabela_precos.valor_global:
        diff = abs(ex.valor_global - processo.tabela_precos.valor_global)
        if diff > _TOLERANCIA:
            r.append(inconforme(
                "Executor Orçamentário", "Valor Global × Tabela",
                f"Executor R$ {ex.valor_global:,.2f} ≠ Tabela R$ {processo.tabela_precos.valor_global:,.2f}.",
            ))
        else:
            r.append(ok("Executor Orçamentário", "Valor Global", "Compatível com Tabela ✓"))
    return r


def _memoria(processo: ProcessoExtraido) -> list[ResultadoItem]:
    mem = processo.memoria_calculo
    if mem is None:
        return [inconforme("Memória de Cálculo", "Presença", "Documento não localizado.")]
    # Saldo disponível validation removed as requested
    return []


def _fiplan(processo: ProcessoExtraido) -> list[ResultadoItem]:
    fp = processo.fiplan
    if fp is None:
        return [inconforme("Demonstrativo FIPLAN", "Presença", "Documento não localizado.")]
    r = []
    if not fp.natureza_despesa:
        r.append(inconforme("Demonstrativo FIPLAN", "Natureza da Despesa", "Campo não identificado."))
    return r


def _gestor(processo: ProcessoExtraido) -> list[ResultadoItem]:
    gst = processo.gestor
    if gst is None:
        return [inconforme("Manifestação do Gestor", "Presença", "Documento não localizado.")]
    r = []

    # Código PDM / Código de Serviços (compras.gov.br)
    if not gst.codigo_pdm:
        r.append(inconforme(
            "Manifestação do Gestor", "Código PDM/Serviços",
            "Código PDM/Código de Serviços ausente. "
            "Verificar no compras.gov.br se o código não está suspenso "
            f"({REGRAS_GESTOR_FISCAL['norma']}).",
        ))
    else:
        r.append(ok("Manifestação do Gestor", "Código PDM/Serviços", gst.codigo_pdm))

    # Segregação de funções: Executor ≠ Fiscal (art. 117, Lei 14.133/2021)
    regras_segregacao = REGRAS_GESTOR_FISCAL["regras"]
    if gst.executor_e_fiscal:
        r.append(inconforme(
            "Manifestação do Gestor", "Segregação de Funções",
            f"'{gst.nome_executor}' é Executor Orçamentário E Fiscal – vedado. "
            f"Regra: {regras_segregacao[2]}. "
            f"Fundamento: {REGRAS_GESTOR_FISCAL['norma']}.",
        ))
    else:
        r.append(ok("Manifestação do Gestor", "Segregação de Funções", "Executor ≠ Fiscal ✓"))

    if not gst.assinou:
        r.append(inconforme("Manifestação do Gestor", "Assinatura", "Assinatura do gestor não localizada."))
    return r


def _ciencias(processo: ProcessoExtraido) -> list[ResultadoItem]:
    if not processo.ciencias:
        return [inconforme(
            "Manifestações de Ciência", "Presença",
            "Nenhuma manifestação de ciência localizada. Obrigatória mesmo sem contrato formal.",
        )]
    r = []
    for idx, ci in enumerate(processo.ciencias, 1):
        if not ci.nome or not ci.funcao or not ci.assinou:
            r.append(inconforme(
                "Manifestações de Ciência", f"Ciência {idx}",
                f"Campos incompletos: nome={ci.nome}, função={ci.funcao}, assinado={ci.assinou}.",
            ))
        else:
            r.append(ok("Manifestações de Ciência", f"Ciência {idx}", f"{ci.nome} ({ci.funcao}) ✓"))
    return r
