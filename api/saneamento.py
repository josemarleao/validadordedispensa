"""Endpoint principal: POST /saneamento/processo"""

from __future__ import annotations
import asyncio
import json
import logging
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from config import settings
from pdf.extractor import extrair_paginas
from pdf.classifier import segmentar_pdf, absorver_desconhecidos
from pdf.ai_classifier import reclassificar_desconhecidos_com_ia
from domain.processo import montar_processo
from rules.saneamento_engine import executar_saneamento_async
from reports.report_builder import construir_resposta
from schemas.responses import RespostaProcessamento
from optimizations.parallel_processor import (
    process_pages_parallel, 
    merge_segment_results, 
    get_processing_stats
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/saneamento", tags=["Saneamento DL"])

_MAX_BYTES = settings.max_pdf_size_mb * 1_048_576


async def reclassificar_desconhecidos_com_ia_parallel(segmentos, batch_size=10):
    """Reclassifica desconhecidos em batches paralelos."""
    desconhecidos = [s for s in segmentos if s.tipo == "DESCONHECIDO"]
    if not desconhecidos:
        return segmentos
    
    # Divide em batches de 10 segmentos
    tasks = []
    for i in range(0, len(desconhecidos), batch_size):
        batch = desconhecidos[i:i + batch_size]
        tasks.append(reclassificar_desconhecidos_com_ia(batch))
    
    # Processa batches em paralelo
    results = await asyncio.gather(*tasks)
    
    # Substitui desconhecidos pelos resultados
    novos_segmentos = []
    desconhecido_idx = 0
    for seg in segmentos:
        if seg.tipo != "DESCONHECIDO":
            novos_segmentos.append(seg)
        else:
            novos_segmentos.append(results[0][desconhecido_idx])
            desconhecido_idx += 1
    
    return novos_segmentos


def _validar_pdf(filename: str | None, pdf_bytes: bytes) -> None:
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")
    if len(pdf_bytes) == 0:
        raise HTTPException(status_code=400, detail="Arquivo PDF vazio.")
    if len(pdf_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"PDF excede o limite de {settings.max_pdf_size_mb} MB.",
        )
    head = pdf_bytes.lstrip(b"\xef\xbb\xbf")[:8]
    if not head.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="O arquivo não parece ser um PDF válido (assinatura %PDF ausente).",
        )


def _normalizar_processo_sei(processo_sei: str) -> str:
    numero = (processo_sei or "").strip()
    if not numero:
        raise HTTPException(
            status_code=422,
            detail="Número SEI do processo é obrigatório e não pode ser vazio.",
        )
    return numero


@router.post(
    "/processo",
    response_model=RespostaProcessamento,
    summary="Saneia processo de Dispensa de Licitação a partir de PDF único",
    description="",
    status_code=status.HTTP_200_OK,
)
async def sanear_processo(
    file: UploadFile = File(..., description="PDF único do processo SEI"),
    processo_sei: str = Form(..., description="Número SEI do processo"),
    unidade_demandante: str = Form("", description="Unidade demandante"),
) -> RespostaProcessamento:

    pdf_bytes = await file.read()
    _validar_pdf(file.filename, pdf_bytes)
    processo_sei = _normalizar_processo_sei(processo_sei)

    log.info(
        "Processando processo=%s | arquivo=%s | tamanho=%d KB",
        processo_sei, file.filename, len(pdf_bytes) // 1024,
    )

    try:
        # Extrair páginas (mantido como sequencial por enquanto)
        paginas = await asyncio.to_thread(
            extrair_paginas, pdf_bytes, settings.ocr_enabled
        )
        if not paginas:
            raise HTTPException(
                status_code=422,
                detail="Nenhuma página pôde ser extraída do PDF. Verifique se o arquivo não está corrompido.",
            )
        if not any(p.tem_texto for p in paginas):
            raise HTTPException(
                status_code=422,
                detail="O PDF não contém texto legível e o OCR não está disponível ou falhou.",
            )

        # Processamento paralelo das páginas
        log.info(f"Iniciando processamento paralelo de {len(paginas)} páginas")
        page_results = await asyncio.to_thread(
            process_pages_parallel, paginas, settings.ocr_enabled, max_workers=8
        )
        
        # Obter estatísticas do processamento
        stats = get_processing_stats(page_results)
        log.info(f"Estatísticas do processamento: {stats}")
        
        # Mesclar resultados das segmentações
        todos_segmentos = merge_segment_results(page_results)
        
        # Classificação com IA (paralelo por batches)
        todos_segmentos = await reclassificar_desconhecidos_com_ia_parallel(todos_segmentos, batch_size=20)
        todos_segmentos = absorver_desconhecidos(todos_segmentos)
        segmentos = [s for s in todos_segmentos if s.tipo != "DESCONHECIDO"]
        
        # Montar processo final
        processo  = await asyncio.to_thread(montar_processo, segmentos, processo_sei, unidade_demandante, len(paginas))
        processo.ocr_utilizado = any(r.via_ocr for r in page_results)
        
        # Adicionar estatísticas ao processo para monitoramento
        processo.processing_stats = stats

        relatorio = await executar_saneamento_async(processo)
        resposta  = await asyncio.to_thread(construir_resposta, processo, relatorio)
        return resposta

    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        log.exception("Erro inesperado no processamento do processo %s", processo_sei)
        raise HTTPException(
            status_code=500,
            detail="Erro interno ao processar o processo. Tente novamente ou contate o suporte.",
        ) from exc


@router.options(
    "/processo/stream",
    summary="CORS preflight support for streaming endpoint",
)
async def sanear_processo_stream_options():
    return {"status": "ok"}

@router.post(
    "/processo/stream",
    summary="Saneia processo com progresso em tempo real (SSE)",
    description="",
)
async def sanear_processo_stream(
    file: UploadFile = File(..., description="PDF único do processo SEI"),
    processo_sei: str = Form(..., description="Número SEI do processo"),
    unidade_demandante: str = Form("", description="Unidade demandante"),
) -> StreamingResponse:

    pdf_bytes = await file.read()
    _validar_pdf(file.filename, pdf_bytes)
    processo_sei = _normalizar_processo_sei(processo_sei)

    log.info(
        "Processando (stream) processo=%s | arquivo=%s | tamanho=%d KB",
        processo_sei, file.filename, len(pdf_bytes) // 1024,
    )

    async def _stream():
        def _sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # Comentário SSE padrão — mantém a conexão viva sem disparar eventos no cliente.
        # Enviado a cada _KA_INTERVAL segundos enquanto aguarda operações longas.
        _KA = ": keepalive\n\n"
        _KA_INTERVAL = 8.0  # segundos

        async def _aguardar(coro):
            """Async generator: envia keepalives enquanto aguarda o coro.

            Yields strings (keepalives) enquanto coro está rodando.
            O último yield é o resultado real (não-string).
            """
            task = asyncio.create_task(coro)
            while not task.done():
                _, pending = await asyncio.wait({task}, timeout=_KA_INTERVAL)
                if pending:
                    yield _KA  # mantém conexão SSE viva
            exc = task.exception()
            if exc:
                raise exc
            yield task.result()  # último item = resultado real

        try:
            # ── Extração ──────────────────────────────────────────────────────
            yield _sse("progresso", {"etapa": "extracao", "mensagem": "Extraindo texto do PDF…"})

            paginas = None
            async for chunk in _aguardar(
                asyncio.to_thread(extrair_paginas, pdf_bytes, settings.ocr_enabled)
            ):
                if isinstance(chunk, str):
                    yield chunk
                else:
                    paginas = chunk

            if not paginas or not any(p.tem_texto for p in paginas):
                yield _sse("erro", {"detail": "PDF sem texto legível ou corrompido."})
                return

            n_ocr = sum(1 for p in paginas if p.via_ocr)
            msg_ocr = f" ({n_ocr} via OCR)" if n_ocr else ""
            yield _sse("progresso", {
                "etapa": "classificacao",
                "mensagem": f"{len(paginas)} página(s) extraída(s){msg_ocr}. Classificando documentos…",
            })

            # ── Classificação determinística (CPU-bound, rápida) ──────────────
            todos_segmentos = await asyncio.to_thread(segmentar_pdf, paginas)

            # ── Reclassificação por IA (I/O-bound, pode ser lenta) ────────────
            n_desconhecidos = sum(1 for s in todos_segmentos if s.tipo == "DESCONHECIDO")
            if n_desconhecidos:
                yield _sse("progresso", {
                    "etapa": "classificacao_ia",
                    "mensagem": f"{n_desconhecidos} bloco(s) não identificado(s) — acionando IA…",
                })
                todos_segmentos_novo = None
                async for chunk in _aguardar(reclassificar_desconhecidos_com_ia(todos_segmentos)):
                    if isinstance(chunk, str):
                        yield chunk
                    else:
                        todos_segmentos_novo = chunk
                todos_segmentos = todos_segmentos_novo

            todos_segmentos = absorver_desconhecidos(todos_segmentos)
            segmentos = [s for s in todos_segmentos if s.tipo != "DESCONHECIDO"]
            tipos = [s.tipo for s in segmentos]
            yield _sse("progresso", {
                "etapa": "extracao_dados",
                "mensagem": f"{len(segmentos)} documento(s) identificado(s): {', '.join(tipos)}. Extraindo dados…",
            })

            # ── Montagem do processo (CPU-bound, rápida) ──────────────────────
            processo = await asyncio.to_thread(
                montar_processo, segmentos, processo_sei, unidade_demandante, len(paginas)
            )
            processo.ocr_utilizado = any(p.via_ocr for p in paginas)

            # ── Saneamento + IA (I/O-bound, pode ser lenta) ───────────────────
            msg_ia = " + análise por IA" if settings.ia_enabled else ""
            yield _sse("progresso", {
                "etapa": "saneamento",
                "mensagem": f"Aplicando regras normativas{msg_ia}…",
            })

            relatorio = None
            async for chunk in _aguardar(executar_saneamento_async(processo)):
                if isinstance(chunk, str):
                    yield chunk
                else:
                    relatorio = chunk

            resposta = await asyncio.to_thread(construir_resposta, processo, relatorio)
            
            # Debug: log response structure
            log.info(f"Enviando resultado - Processo: {processo.numero_sei}, "
                    f"Relatório tem {len(relatorio.inconformidades)} inconformes, "
                    f"{len(relatorio.pendencias)} pendências, "
                    f"{len(relatorio.documentos_conformes)} conformes")
            
            yield _sse("resultado", resposta.model_dump(mode="json"))
            log.info("Resultado enviado via SSE")

        except Exception:
            log.exception("Erro no stream do processo %s", processo_sei)
            yield _sse(
                "erro",
                {"detail": "Erro interno ao processar o processo. Tente novamente ou contate o suporte."},
            )

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )



@router.get("/health", summary="Verificação de disponibilidade")
async def health():
    """Verifica se a IA está configurada e faz um teste simples."""
    from config import settings
    from ai.analyzer import analisar
    
    resultado = {
        "status": "ok",
        "servico": "Saneamento DL – MPBA",
        "azure_storage": settings.azure_storage_enabled,
        "ocr_enabled": settings.ocr_enabled,
        "ia_enabled": settings.ia_enabled,
        "ia_configured": bool(settings.openrouter_api_key),
        "ia_model": settings.ia_model if settings.ia_enabled else None,
        "ia_test": None,
        "ia_test_error": None,
    }
    
    # Teste rápido da IA se estiver configurada
    if settings.ia_enabled and settings.openrouter_api_key:
        try:
            resposta = await analisar(
                "Responda APENAS com JSON: {\"status\": \"ok\"}",
                "Teste rápido",
                max_tokens=50
            )
            if resposta:
                resultado["ia_test"] = "sucesso"
                resultado["ia_test_result"] = resposta
            else:
                resultado["ia_test"] = "falhou - IA retornou None"
        except Exception as exc:
            resultado["ia_test"] = "erro"
            resultado["ia_test_error"] = str(exc)
            resultado["ia_test_error_type"] = type(exc).__name__
    
    return resultado


@router.get("/test-ia", summary="Testa se a IA está funcionando")
async def test_ia():
    """Testa a configuração da IA e faz uma chamada simples."""
    from config import settings
    from ai.analyzer import analisar
    
    resultado = {
        "ia_enabled": settings.ia_enabled,
        "ia_model": settings.ia_model,
        "openrouter_api_key_present": bool(settings.openrouter_api_key),
        "test_result": None,
        "test_error": None,
    }
    
    if not settings.ia_enabled:
        resultado["test_error"] = "IA não está habilitada (ia_enabled=false)"
        return resultado
    
    if not settings.openrouter_api_key:
        resultado["test_error"] = "API key do OpenRouter não configurada"
        return resultado
    
    try:
        # Teste simples: pergunta à IA para responder com JSON
        resposta = await analisar(
            "Responda APENAS com JSON: {\"status\": \"ok\", \"mensagem\": \"IA funcionando\"}",
            "Teste de conexão",
            max_tokens=100
        )
        resultado["test_result"] = resposta
        if resposta:
            resultado["status"] = "sucesso"
        else:
            resultado["test_error"] = "IA retornou None (possível erro na chamada)"
    except Exception as exc:
        resultado["test_error"] = f"Erro ao chamar IA: {str(exc)}"
    
    return resultado
