"""Construtor do relatório."""

from __future__ import annotations
from schemas.responses import RelatorioSaneamento, RespostaProcessamento
from domain.processo import ProcessoExtraido


def construir_resposta(
    processo: ProcessoExtraido,
    relatorio: RelatorioSaneamento,
) -> RespostaProcessamento:
    return RespostaProcessamento(
        processo_sei=processo.numero_sei,
        relatorio=relatorio,
        documentos_identificados=processo.documentos_encontrados,
        paginas_processadas=processo.paginas_processadas,
        ocr_utilizado=processo.ocr_utilizado,
    )
