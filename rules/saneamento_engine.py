"""Motor de saneamento: orquestra todas as regras e gera o relatório."""

from __future__ import annotations
import logging
from domain.processo import ProcessoExtraido
from schemas.responses import (
    RelatorioSaneamento,
    Encaminhamento,
    StatusRegra,
    ResultadoItem,
    ResumoContagens,
    Providencia,
)
from .dfd_rules        import aplicar_regras_dfd
from .tr_rules         import aplicar_regras_tr
from .precos_rules     import aplicar_regras_precos
from .orcamentos_rules import aplicar_regras_orcamentos
from .certidoes_rules  import aplicar_regras_certidoes, aplicar_regras_empresa
from .orcamentarias_rules import aplicar_regras_orcamentarias

log = logging.getLogger(__name__)


def _coletar_deterministicos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    """Executa todas as regras determinísticas e retorna a lista bruta."""
    todos: list[ResultadoItem] = []
    todos += aplicar_regras_dfd(processo)
    todos += aplicar_regras_tr(processo)
    todos += aplicar_regras_precos(processo)
    todos += aplicar_regras_orcamentos(processo)
    todos += aplicar_regras_certidoes(processo)
    todos += aplicar_regras_empresa(processo)
    todos += aplicar_regras_orcamentarias(processo)
    return todos


async def _coletar_deterministicos_parallel(processo: ProcessoExtraido) -> list[ResultadoItem]:
    """Executa todas as regras determinísticas em paralelo e retorna a lista bruta."""
    import asyncio
    
    tasks = [
        asyncio.to_thread(aplicar_regras_dfd, processo),
        asyncio.to_thread(aplicar_regras_tr, processo),
        asyncio.to_thread(aplicar_regras_precos, processo),
        asyncio.to_thread(aplicar_regras_orcamentos, processo),
        asyncio.to_thread(aplicar_regras_certidoes, processo),
        asyncio.to_thread(aplicar_regras_empresa, processo),
        asyncio.to_thread(aplicar_regras_orcamentarias, processo),
    ]
    results = await asyncio.gather(*tasks)
    return [item for sublist in results for item in sublist]


def _montar_relatorio(processo: ProcessoExtraido, todos: list[ResultadoItem]) -> RelatorioSaneamento:
    """Constrói o RelatorioSaneamento a partir da lista final de ResultadoItem."""
    inconformidades = [r for r in todos if r.status == StatusRegra.INCONFORME]
    pendencias      = [r for r in todos if r.status == StatusRegra.PENDENCIA]
    conformes       = [r for r in todos if r.status == StatusRegra.CONFORME]

    # Documentos cujos checks foram todos conformes
    docs_inconf = {r.documento for r in inconformidades + pendencias}
    docs_ok = sorted({r.documento for r in conformes} - docs_inconf)

    encaminhamento = _encaminhamento(inconformidades, pendencias)

    resumo = ResumoContagens(
        inconformidades=len(inconformidades),
        pendencias=len(pendencias),
        conformes=len(conformes),
    )

    obs = None
    total = len(inconformidades) + len(pendencias)
    if total == 0:
        obs = "Processo em conformidade com os requisitos normativos verificados automaticamente."
    else:
        obs = (
            f"{len(inconformidades)} inconformidade(s) e {len(pendencias)} pendência(s) "
            "identificadas pela análise automatizada. Verificação humana recomendada."
        )

    log.info(
        "Saneamento concluído: %d inconf. | %d pend.",
        len(inconformidades), len(pendencias),
    )

    return RelatorioSaneamento(
        processo=processo.numero_sei,
        tipo=_tipo_processo(processo),
        resumo=resumo,
        inconformidades=inconformidades,
        pendencias=pendencias,
        documentos_conformes=docs_ok,
        encaminhamento=encaminhamento,
        observacoes=obs,
    )


def _tipo_processo(processo: ProcessoExtraido) -> str:
    """Determina o tipo do processo para exibição no relatório."""
    from domain.tr_unificado import TRServicosExtraido, TRAquisicoesExtraido

    if isinstance(processo.tr, TRAquisicoesExtraido):
        return "DL não eletrônica – Aquisições"
    if isinstance(processo.tr, TRServicosExtraido):
        return "DL não eletrônica – Serviços"
    return "DL não eletrônica"


def _encaminhamento(
    inconformidades: list[ResultadoItem],
    pendencias: list[ResultadoItem],
) -> Encaminhamento:
    todas = inconformidades + pendencias
    if any(r.providencia == Providencia.SGA for r in todas):
        return Encaminhamento.SGA
    if any(r.providencia == Providencia.CORRIGIR for r in todas):
        return Encaminhamento.UNIDADE_DEMANDANTE
    if inconformidades:
        return Encaminhamento.UNIDADE_DEMANDANTE
    return Encaminhamento.PROSSEGUIR


# ─────────────────────────────────────────────────────────────────────────────
# Pontos de entrada públicos
# ─────────────────────────────────────────────────────────────────────────────

def executar_saneamento(processo: ProcessoExtraido) -> RelatorioSaneamento:
    """Aplica regras determinísticas e retorna o relatório (síncrono)."""
    log.info("Iniciando saneamento do processo %s", processo.numero_sei)
    todos = _coletar_deterministicos(processo)
    return _montar_relatorio(processo, todos)


async def executar_saneamento_async(processo: ProcessoExtraido) -> RelatorioSaneamento:
    """Aplica regras determinísticas + análise subsidiária por IA (assíncrono)."""
    import asyncio
    from config import settings

    log.info("Iniciando saneamento (async) do processo %s", processo.numero_sei)
    log.info("Configurações IA - ia_enabled=%s, ia_model=%s, kilo_api_key_configurada=%s", 
             settings.ia_enabled, settings.ia_model, bool(settings.kilo_api_key))

    # Regras determinísticas em paralelo (CPU-bound)
    deterministicos = await _coletar_deterministicos_parallel(processo)

    # Verifica se API key do Kilo AI está configurada
    api_key_configurada = bool(settings.kilo_api_key)
    log.info("API key configurada: %s", api_key_configurada)
    
    # Análise OBRIGATÓRIA de DFD (Coerência DFD × TR) pela IA - sempre executada se API key configurada
    novos_ia_dfd = []
    if api_key_configurada and processo.dfd and processo.dfd.texto_original:
        try:
            from .ia_rules import _analisar_dfd
            novos_ia_dfd = await _analisar_dfd(processo)
            log.info("Análise obrigatória de DFD (Coerência DFD × TR) executada: %d item(ns)", len(novos_ia_dfd))
        except Exception as exc:
            log.warning("Análise obrigatória de DFD falhou: %s", exc)
    
    # Análise opcional por IA (TR, tabela de preços, orçamentos) - somente se habilitada
    novos_ia_opcionais = []
    if settings.ia_enabled and api_key_configurada:
        try:
            from .ia_rules import aplicar_regras_ia, double_check_inconformidades

            # Fase 1: IA resolve PENDÊNCIAs e acrescenta análise qualitativa (exceto DFD que já foi analisado)
            # Passamos deterministicos + novos_ia_dfd para evitar duplicação
            deterministicos_sem_dfd_ia = [r for r in deterministicos if not (r.documento == "DFD" and r.item == "Coerência DFD × TR")]
            deterministicos_filtrados, novos_ia_opcionais = await aplicar_regras_ia(processo, deterministicos_sem_dfd_ia)
            novos_ia_opcionais = [r for r in novos_ia_opcionais if not (r.documento == "DFD" and r.item == "Coerência DFD × TR")]
            
            todos = deterministicos + novos_ia_dfd + novos_ia_opcionais
            log.info("IA opcional acrescentou %d item(ns) ao relatório.", len(novos_ia_opcionais))

            # Fase 2: double-check — IA confirma ou descarta cada INCONFORME/PENDÊNCIA
            todos = await double_check_inconformidades(processo, todos)
        except Exception as exc:
            log.warning("Análise opcional por IA falhou: %s – usando análise obrigatória de DFD + regras determinísticas.", exc)
            todos = deterministicos + novos_ia_dfd
    else:
        todos = deterministicos + novos_ia_dfd

    return _montar_relatorio(processo, todos)
