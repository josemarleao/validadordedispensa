"""Cliente Google Gemini e OpenRouter para análise subsidiária de documentos de DL."""

from __future__ import annotations
import asyncio
import json
import logging
import threading
from typing import Any, Optional

log = logging.getLogger(__name__)

_client_lock = threading.Lock()
_genai_client: Any = None
_openrouter_client: Any = None


def _get_genai_client() -> Any:
    """Reutiliza um único cliente HTTP (menos overhead e mais estável sob carga)."""
    global _genai_client
    from config import settings

    with _client_lock:
        if _genai_client is None:
            from google import genai

            _genai_client = genai.Client(api_key=settings.gemini_api_key)
        return _genai_client


def _get_openrouter_client() -> Any:
    """Reutiliza um único cliente OpenRouter."""
    global _openrouter_client
    from config import settings

    with _client_lock:
        if _openrouter_client is None:
            from openai import OpenAI

            _openrouter_client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
            )
        return _openrouter_client

_SISTEMA = (
    "Você é um analista especializado em conformidade de processos de "
    "Dispensa de Licitação (DL) do Ministério Público da Bahia (MPBA), "
    "com base na Lei nº 14.133/2021 e nos modelos normativos MPBA Jan/2026. "
    "Analise os trechos fornecidos e responda APENAS com JSON válido, sem texto adicional."
)


def _limite_contexto_chars(ia_model: str) -> int:
    """Gemma costuma ter janela menor que Gemini; evita rejeição por contexto excedido."""
    m = (ia_model or "").lower()
    if m.startswith("gemma"):
        return 120_000
    return 400_000


def _config_geracao(max_tokens: int, ia_model: str) -> Any:
    from google.genai import types

    m = (ia_model or "").lower()
    # Thinking é específico de famílias Gemini 2.5+; Gemma rejeita / ignora de forma inconsistente.
    if m.startswith("gemma"):
        return types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.1,
        )
    return types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=max_tokens,
        temperature=0.1,
    )


def _get_openrouter_model() -> str:
    """Retorna o modelo OpenRouter a ser usado."""
    from config import settings
    model = settings.ia_model
    log.info("Lendo modelo das configurações: ia_model='%s'", model)
    if model:
        return model
    log.error("Modelo IA não configurado (ia_model está vazio)")
    return None


async def analisar(
    pergunta: str,
    contexto: str,
    max_tokens: int = 512,
) -> Optional[dict[str, Any]]:
    """Envia prompt ao Gemini ou OpenRouter e retorna JSON parseado, ou None se IA desabilitada/falhar."""
    import asyncio
    from config import settings

    log.info("analisar() chamado - ia_enabled=%s, ia_provider=%s, gemini_api_key_present=%s, openrouter_api_key_present=%s", 
             settings.ia_enabled, settings.ia_provider, bool(settings.gemini_api_key), bool(settings.openrouter_api_key))
    
    if not settings.ia_enabled:
        log.warning("IA desabilitada, retornando None")
        return None
    
    # Verifica qual provider está configurado
    provider = settings.ia_provider.lower()
    
    if provider == "openrouter":
        if not settings.openrouter_api_key:
            log.warning("OpenRouter habilitado mas API key não configurada, retornando None")
            return None
        log.info("Chamando _analisar_openrouter com contexto de %d chars", len(contexto))
        resultado = await _analisar_openrouter(pergunta, contexto, max_tokens)
    else:  # gemini (padrão)
        if not settings.gemini_api_key:
            log.warning("Gemini habilitado mas API key não configurada, retornando None")
            return None
        log.info("Chamando _analisar_gemini com contexto de %d chars", len(contexto))
        resultado = await _analisar_gemini(pergunta, contexto, max_tokens)
    
    log.info("analisar() retornou: %s", "sucesso" if resultado else "None")
    return resultado


async def _analisar_gemini(
    pergunta: str,
    contexto: str,
    max_tokens: int = 512,
) -> Optional[dict[str, Any]]:
    """Envia prompt ao Gemini e retorna JSON parseado."""
    import asyncio
    from config import settings

    # O chamador (ia_rules.py) é responsável por pré-fatiar o contexto ao
    # que é relevante para cada pergunta. Aqui apenas aplicamos um limite de
    # segurança contra entradas absurdamente grandes, preservando início e fim.
    safety = _limite_contexto_chars(settings.ia_model)
    if len(contexto) > safety:
        metade = safety // 2
        log.warning("Contexto excede %d chars (%d); truncando.", safety, len(contexto))
        contexto_usado = contexto[:metade] + "\n\n[...]\n\n" + contexto[-metade:]
    else:
        contexto_usado = contexto
    prompt = f"{_SISTEMA}\n\n{pergunta}\n\nTEXTO:\n{contexto_usado}"

    last_error: Exception | None = None
    # Retry com backoff exponencial (150s, 300s)
    timeouts = [90.0, 150.0]
    for attempt in range(len(timeouts)):
        try:
            client = _get_genai_client()
            cfg = _config_geracao(max_tokens, settings.ia_model)
            timeout = timeouts[attempt]
            resp = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=settings.ia_model,
                    contents=prompt,
                    config=cfg,
                ),
                timeout=timeout,
            )
            # Acessa o texto de todos os parts do candidato (evita truncagem de resp.text)
            txt = ""
            finish_reason = None
            try:
                cand = resp.candidates[0]
                finish_reason = getattr(cand, "finish_reason", None)
                for part in cand.content.parts:
                    txt += part.text or ""
            except Exception:
                txt = resp.text or ""
            txt = txt.strip()

            log.info(
                "Gemini resposta raw (%d chars) finish_reason=%s: %.400s",
                len(txt), finish_reason, txt,
            )

            if not txt:
                log.warning("Gemini retornou resposta vazia.")
                if attempt == 0:
                    continue
                return None
            # Remove delimitadores de bloco de código, se presentes
            if "```json" in txt:
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif "```" in txt:
                txt = txt.split("```")[1].split("```")[0].strip()
            # Extrai o objeto JSON (ignora texto antes/depois)
            inicio = txt.find("{")
            fim = txt.rfind("}") + 1
            if inicio >= 0 and fim > inicio:
                txt = txt[inicio:fim]
            return json.loads(txt)
        except json.JSONDecodeError as exc:
            last_error = exc
            log.warning("JSON do Gemini inválido (tentativa %d/%d): %s", attempt + 1, len(timeouts), exc)
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)  # Backoff: 1s, 2s, 4s...
                continue
            return None
        except asyncio.TimeoutError as exc:
            last_error = exc
            log.warning("Timeout do Gemini (tentativa %d/%d, timeout=%.1fs)", attempt + 1, len(timeouts), timeouts[attempt])
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None
        except Exception as exc:
            last_error = exc
            log.warning("Análise por Gemini falhou (tentativa %d/%d): %s", attempt + 1, len(timeouts), exc)
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return None

    if last_error:
        log.warning("Análise por Gemini esgotou tentativas: %s", last_error)
    return None


async def _analisar_openrouter(
    pergunta: str,
    contexto: str,
    max_tokens: int = 512,
) -> Optional[dict[str, Any]]:
    """Envia prompt ao OpenRouter e retorna JSON parseado."""
    import asyncio
    from config import settings

    log.info("Iniciando análise OpenRouter - Model: %s", settings.ia_model)
    
    # Trunca contexto se necessário (OpenRouter free models têm limites)
    safety = 120_000  # limite conservador para modelos free
    if len(contexto) > safety:
        metade = safety // 2
        log.warning("Contexto excede %d chars (%d); truncando.", safety, len(contexto))
        contexto_usado = contexto[:metade] + "\n\n[...]\n\n" + contexto[-metade:]
    else:
        contexto_usado = contexto
    
    last_error: Exception | None = None
    raw_response: str = ""
    # Retry com backoff exponencial
    timeouts = [90.0, 150.0]
    model = _get_openrouter_model()
    
    if not model:
        log.error("Modelo IA não configurado (ia_model está vazio)")
        return {"error": "model_not_configured", "error_message": "IA_MODEL não está configurado"}
    
    log.info("Usando modelo OpenRouter: %s", model)
    
    for attempt in range(len(timeouts)):
        try:
            client = _get_openrouter_client()
            timeout = timeouts[attempt]
            
            log.info("Tentativa %d/%d - Enviando requisição para OpenRouter", attempt + 1, len(timeouts))
            log.info("Pergunta: %.100s", pergunta)
            log.info("Contexto: %.100s", contexto_usado[:100])
            
            # Usa asyncio para rodar chamada síncrona do OpenAI em thread separada
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": _SISTEMA},
                        {"role": "user", "content": f"{pergunta}\n\nTEXTO:\n{contexto_usado}"}
                    ],
                    max_tokens=max_tokens,
                    temperature=0.1,
                )
            )
            
            txt = resp.choices[0].message.content or ""
            txt = txt.strip()
            raw_response = txt

            log.info(
                "OpenRouter resposta recebida (%d chars): %.400s",
                len(txt), txt,
            )

            if not txt:
                log.warning("OpenRouter retornou resposta vazia.")
                if attempt == 0:
                    continue
                # Retornar dict com erro para debug
                return {"error": "empty_response", "raw_response": raw_response}
            # Remove delimitadores de bloco de código, se presentes
            if "```json" in txt:
                txt = txt.split("```json")[1].split("```")[0].strip()
            elif "```" in txt:
                txt = txt.split("```")[1].split("```")[0].strip()
            # Extrai o objeto JSON (ignora texto antes/depois)
            inicio = txt.find("{")
            fim = txt.rfind("}") + 1
            if inicio >= 0 and fim > inicio:
                txt = txt[inicio:fim]
            result = json.loads(txt)
            log.info("JSON parseado com sucesso: %s", result)
            return result
        except json.JSONDecodeError as exc:
            last_error = exc
            log.warning("JSON do OpenRouter inválido (tentativa %d/%d): %s - Resposta: %.200s", attempt + 1, len(timeouts), exc, txt[:200] if 'txt' in locals() else "N/A")
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            # Retornar dict com erro para debug
            return {"error": "json_decode", "error_message": str(exc), "raw_response": raw_response[:500]}
        except asyncio.TimeoutError as exc:
            last_error = exc
            log.warning("Timeout do OpenRouter (tentativa %d/%d, timeout=%.1fs)", attempt + 1, len(timeouts), timeouts[attempt])
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "timeout", "error_message": str(exc)}
        except Exception as exc:
            last_error = exc
            log.error("Análise por OpenRouter falhou (tentativa %d/%d): %s - Tipo: %s - Detalhes: %s", attempt + 1, len(timeouts), str(exc), type(exc).__name__, str(exc.__dict__) if hasattr(exc, '__dict__') else "")
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "exception", "error_message": str(exc), "error_type": type(exc).__name__}

    if last_error:
        log.error("Análise por OpenRouter esgotou tentativas: %s", last_error)
    return {"error": "exhausted_retries", "last_error": str(last_error) if last_error else "unknown"}
