"""Classificação de documentos via IA – fallback para segmentos não identificados por keywords."""

from __future__ import annotations
import asyncio
import logging
from pdf.extractor import DocumentoExtraido

log = logging.getLogger(__name__)

_TIPOS_DESCRICAO = """
- DFD: Documento de Formalização da Demanda (descreve a necessidade e justifica a contratação)
- TR_SERVICOS: Termo de Referência de Serviços (contém objeto, regime de execução, local, fiscal)
- TR_AQUISICOES: Termo de Referência de Aquisições/Compras (contém objeto, local de entrega, marca/modelo)
- TABELA_PRECOS: Tabela de Preços Orçados (pesquisa de mercado com fornecedores consultados e menor preço)
- ORCAMENTO: Orçamento ou Proposta Comercial de empresa (razão social, CNPJ, valor, validade)
- CARTAO_CNPJ: Cartão CNPJ – Comprovante de Inscrição e Situação Cadastral (Receita Federal)
- CONTRATO_SOCIAL: Contrato Social ou Estatuto Social da empresa (junta comercial, sócios)
- SICAF: Consulta/Extrato do SICAF (Sistema de Cadastramento Unificado de Fornecedores)
- CERTIDAO: Certidão de regularidade fiscal ou trabalhista (PGFN, Receita, FGTS/CRF, CNDT, Estadual, Municipal)
- COMPROVANTE_BANCARIO: Comprovante de conta bancária (dados bancários, agência, conta corrente)
- DECLARACAO: Declaração (não emprego de menor – art. 7º CF; Resolução CNMP nº 37/2009)
- EXECUTOR_ORCAMENTARIO: Formulário de Executor Orçamentário (dotação, fonte de recursos, impacto orçamentário)
- MEMORIA_CALCULO: Memória de Cálculo do teto de contratação (art. 75 §1, contratações anteriores)
- DEMONSTRATIVO_FIPLAN: Demonstrativo de Disponibilidade Orçamentária via FIPLAN
- MANIFESTACAO_GESTOR: Manifestação do Gestor Orçamentário (designação de fiscal administrativo/técnico)
- MANIFESTACAO_CIENCIA: Manifestação de Ciência (declaração de ciência do fiscal ou gestor do contrato)
- DESCONHECIDO: Não foi possível identificar o tipo do documento
"""

# Tipos válidos para validação da resposta
_TIPOS_VALIDOS = {
    "DFD", "TR_SERVICOS", "TR_AQUISICOES", "TABELA_PRECOS", "ORCAMENTO",
    "CARTAO_CNPJ", "CONTRATO_SOCIAL", "SICAF", "CERTIDAO", "COMPROVANTE_BANCARIO",
    "DECLARACAO", "EXECUTOR_ORCAMENTARIO", "MEMORIA_CALCULO", "DEMONSTRATIVO_FIPLAN",
    "MANIFESTACAO_GESTOR", "MANIFESTACAO_CIENCIA", "DESCONHECIDO",
}


# Semaphore para limitar concorrência de requisições à IA (máx 6 simultâneas)
_IA_SEMAPHORE = asyncio.Semaphore(6)


async def reclassificar_desconhecidos_com_ia(
    segmentos: list[DocumentoExtraido],
) -> list[DocumentoExtraido]:
    """Tenta reclassificar via IA os segmentos DESCONHECIDO que possuem texto.

    Retorna a lista completa com os segmentos DESCONHECIDO substituídos
    pelo tipo identificado pela IA (quando possível).
    
    Usa semaphore para evitar sobrecarregar a API com muitas requisições simultâneas
    em documentos extensos.
    """
    from config import settings

    # Verifica qual provider está configurado e se a API key correspondente está presente
    provider = settings.ia_provider.lower()
    api_key_configurada = bool(settings.gemini_api_key) if provider == "gemini" else bool(settings.openrouter_api_key)
    
    if not settings.ia_enabled or not api_key_configurada:
        return segmentos

    candidatos = [
        (i, seg) for i, seg in enumerate(segmentos)
        if seg.tipo == "DESCONHECIDO" and len(seg.texto_completo.strip()) > 100
    ]

    if not candidatos:
        return segmentos

    log.info("IA: reclassificando %d segmento(s) DESCONHECIDO.", len(candidatos))

    # Usar semaphore para limitar concorrência: máx 3 classificações simultâneas
    tasks = [_classificar_segmento_com_semaphore(seg) for _, seg in candidatos]
    resultados = await asyncio.gather(*tasks, return_exceptions=True)

    novos = list(segmentos)
    for (idx, seg), resultado in zip(candidatos, resultados):
        if isinstance(resultado, Exception):
            log.warning("IA falhou ao classificar páginas %s: %s", seg.paginas, resultado)
            continue
        if resultado and resultado != "DESCONHECIDO":
            log.info(
                "IA reclassificou páginas %s: DESCONHECIDO → %s (conf=0.5)",
                seg.paginas, resultado,
            )
            novos[idx] = DocumentoExtraido(
                tipo=resultado,
                paginas=seg.paginas,
                texto_completo=seg.texto_completo,
                confianca=0.5,
                textos_paginas=seg.textos_paginas,  # preserva para divisão de orçamentos
            )

    return novos


async def _classificar_segmento_com_semaphore(seg: DocumentoExtraido) -> str:
    """Classifica um segmento com semaphore para evitar sobrecarregar a IA."""
    async with _IA_SEMAPHORE:
        return await _classificar_segmento(seg)


async def _classificar_segmento(seg: DocumentoExtraido) -> str:
    """Pergunta à IA o tipo do documento e retorna o nome do tipo ou 'DESCONHECIDO'."""
    from ai.analyzer import analisar

    # Contexto: início (onde fica o título/tipo) + fim (onde fica rodapé/assinatura).
    # Documentos longos como TR têm o tipo identificável no cabeçalho; certidões
    # têm informações críticas também no rodapé.
    texto = seg.texto_completo
    if len(texto) > 4000:
        amostra = texto[:3000] + "\n\n[...]\n\n" + texto[-1000:]
    else:
        amostra = texto

    pergunta = f"""Você está analisando um documento de um processo de Dispensa de Licitação (DL) \
do Ministério Público da Bahia (MPBA).

Com base no texto abaixo, identifique o tipo do documento escolhendo UMA das opções:
{_TIPOS_DESCRICAO}

Responda APENAS com JSON: {{"tipo": "NOME_EXATO_DO_TIPO"}}"""

    resultado = await analisar(pergunta, amostra, max_tokens=60)

    if isinstance(resultado, dict):
        tipo = str(resultado.get("tipo", "")).strip()
        if tipo in _TIPOS_VALIDOS:
            return tipo

    return "DESCONHECIDO"
