"""Endpoint principal: POST /saneamento/processo

A extração de texto, identificação de documentos, prompts e análise por IA
acontecem inteiramente no fluxo do Power Automate. Esta API só valida o
upload, reenvia o PDF para o fluxo e devolve a resposta dele ao cliente.
"""

from __future__ import annotations
import asyncio
import base64
import json
import logging
import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from config import settings
from schemas.responses import (
    Encaminhamento,
    Providencia,
    RelatorioSaneamento,
    ResultadoItem,
    RespostaProcessamento,
    ResumoContagens,
    StatusRegra,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/saneamento", tags=["Saneamento DL"])

_MAX_BYTES = settings.max_pdf_size_mb * 1_048_576

_STATUS_MAP = {
    "CONFORME": StatusRegra.CONFORME,
    "NÃO CONFORME": StatusRegra.INCONFORME,
    "PENDÊNCIA": StatusRegra.PENDENCIA,
}

_PROVIDENCIA_MAP = {
    "Prosseguir": Providencia.PROSSEGUIR,
    "Corrigir": Providencia.CORRIGIR,
    "Submeter à SGA": Providencia.SGA,
}


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


async def _enviar_para_power_automate(
    pdf_bytes: bytes,
    filename: str,
    processo_sei: str,
    unidade_demandante: str,
) -> dict:
    """Envia o PDF ao fluxo do Power Automate e retorna o JSON de análise (ver Prompt, Seção 9).

    O gatilho do fluxo ("Quando uma solicitação HTTP é recebida") espera um corpo JSON
    com o PDF em base64 — não multipart/form-data.
    """
    if not settings.power_automate_processo_url:
        raise RuntimeError("Fluxo de processamento (Power Automate) não configurado.")

    payload = {
        "file_content_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        "file_name": filename,
        "processo_sei": processo_sei,
        "unidade_demandante": unidade_demandante,
    }

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(settings.power_automate_processo_url, json=payload)
    resp.raise_for_status()
    return resp.json()


def _montar_resposta(bruto: dict, processo_sei: str) -> RespostaProcessamento:
    """Converte o JSON de análise da IA (Prompt, Seção 9) em RespostaProcessamento."""
    todos: list[ResultadoItem] = []
    for it in bruto.get("itens", []):
        status_regra = _STATUS_MAP.get(it.get("status"))
        if status_regra is None:
            log.warning("Item com status desconhecido ignorado: %r", it)
            continue
        providencia = _PROVIDENCIA_MAP.get(it.get("providencia"), Providencia.CORRIGIR)
        todos.append(ResultadoItem(
            documento=it.get("documento", ""),
            item=it.get("item", ""),
            status=status_regra,
            descricao=it.get("descricao", ""),
            providencia=providencia,
            via_ia=True,
        ))

    inconformidades = [r for r in todos if r.status == StatusRegra.INCONFORME]
    pendencias = [r for r in todos if r.status == StatusRegra.PENDENCIA]
    conformes = [r for r in todos if r.status == StatusRegra.CONFORME]

    docs_com_problema = {r.documento for r in inconformidades + pendencias}
    documentos_conformes = sorted({r.documento for r in conformes} - docs_com_problema)

    problematicos = inconformidades + pendencias
    if any(r.providencia == Providencia.SGA for r in problematicos):
        encaminhamento = Encaminhamento.SGA
    elif any(r.providencia == Providencia.CORRIGIR for r in problematicos):
        encaminhamento = Encaminhamento.UNIDADE_DEMANDANTE
    elif inconformidades:
        encaminhamento = Encaminhamento.UNIDADE_DEMANDANTE
    else:
        encaminhamento = Encaminhamento.PROSSEGUIR

    relatorio = RelatorioSaneamento(
        processo=processo_sei,
        tipo=bruto.get("tipo_processo") or "DL não eletrônica",
        resumo=ResumoContagens(
            inconformidades=len(inconformidades),
            pendencias=len(pendencias),
            conformes=len(conformes),
        ),
        inconformidades=inconformidades,
        pendencias=pendencias,
        documentos_conformes=documentos_conformes,
        encaminhamento=encaminhamento,
        observacoes=bruto.get("observacoes"),
    )

    return RespostaProcessamento(
        processo_sei=processo_sei,
        relatorio=relatorio,
        documentos_identificados=bruto.get("documentos_identificados", []),
        paginas_processadas=bruto.get("paginas_processadas", 0),
        ocr_utilizado=bool(bruto.get("ocr_utilizado", False)),
    )


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
        resultado = await _enviar_para_power_automate(pdf_bytes, file.filename, processo_sei, unidade_demandante)
        return _montar_resposta(resultado, processo_sei)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        log.exception("Erro ao comunicar com o fluxo Power Automate para o processo %s", processo_sei)
        raise HTTPException(status_code=502, detail="Erro ao processar o documento no fluxo externo.") from exc
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
        # Enviado a cada _KA_INTERVAL segundos enquanto aguarda o fluxo do Power Automate.
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
            yield _sse("progresso", {
                "etapa": "processamento",
                "mensagem": "Documento enviado para análise…",
            })

            resultado_dict = None
            async for chunk in _aguardar(
                _enviar_para_power_automate(pdf_bytes, file.filename, processo_sei, unidade_demandante)
            ):
                if isinstance(chunk, str):
                    yield chunk
                else:
                    resultado_dict = chunk

            resposta = _montar_resposta(resultado_dict, processo_sei)
            yield _sse("resultado", resposta.model_dump(mode="json"))
            log.info("Resultado enviado via SSE")

        except RuntimeError as exc:
            log.error("Fluxo Power Automate não configurado: %s", exc)
            yield _sse("erro", {"detail": str(exc)})
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
    return {
        "status": "ok",
        "servico": "Saneamento DL – MPBA",
        "power_automate_configurado": bool(settings.power_automate_processo_url),
    }
