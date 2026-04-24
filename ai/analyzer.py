"""Cliente Kilo AI para análise subsidiária de documentos de DL."""

from __future__ import annotations
import asyncio
import json
import logging
import threading
from typing import Any, Optional

log = logging.getLogger(__name__)

_client_lock = threading.Lock()
_kilo_client: Any = None


def _get_kilo_client() -> Any:
    """Reutiliza um único cliente Kilo AI."""
    global _kilo_client
    from config import settings

    with _client_lock:
        if _kilo_client is None:
            from openai import OpenAI

            _kilo_client = OpenAI(
                base_url=settings.kilo_base_url,
                api_key=settings.kilo_api_key,
            )
        return _kilo_client

_SISTEMA = (
    "Você é um analista especializado em conformidade de processos de "
    "Dispensa de Licitação (DL) do Ministério Público da Bahia (MPBA), "
    "com base na Lei nº 14.133/2021 e nos modelos normativos MPBA Jan/2026. "
    "Analise os trechos fornecidos e responda APENAS com JSON válido, sem texto adicional."
)


def _get_kilo_model() -> str:
    """Retorna o modelo Kilo AI a ser usado."""
    from config import settings
    # Usa o modelo configurado no secret
    model = settings.ia_model
    log.info("Lendo modelo das configurações: ia_model='%s'", model)
    if model:
        return model
    # Fallback para modelo mais estável
    log.warning("IA_MODEL não configurado, usando fallback")
    return "anthropic/claude-3-haiku"


async def analisar(
    pergunta: str,
    contexto: str,
    max_tokens: int = 512,
) -> Optional[dict[str, Any]]:
    """Envia prompt ao Kilo AI e retorna JSON parseado, ou None se IA desabilitada/falhar."""
    import asyncio
    from config import settings

    log.info("analisar() chamado - ia_enabled=%s, kilo_api_key_present=%s", 
             settings.ia_enabled, bool(settings.kilo_api_key))
    
    if not settings.ia_enabled:
        log.warning("IA desabilitada, retornando None")
        return None
    
    if not settings.kilo_api_key:
        log.warning("Kilo AI habilitado mas API key não configurada, retornando None")
        return None
    
    log.info("Chamando _analisar_kilo com contexto de %d chars", len(contexto))
    resultado = await _analisar_kilo(pergunta, contexto, max_tokens)
    log.info("analisar() retornou: %s", "sucesso" if resultado else "None")
    return resultado


async def _analisar_kilo(
    pergunta: str,
    contexto: str,
    max_tokens: int = 512,
) -> Optional[dict[str, Any]]:
    """Envia prompt ao Kilo AI e retorna JSON parseado."""
    import asyncio
    from config import settings

    log.info("Iniciando análise Kilo AI - Model: %s", settings.ia_model)
    
    # Trunca contexto se necessário
    safety = 120_000
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
    model = _get_kilo_model()
    
    if not model:
        log.error("Modelo IA não configurado (ia_model está vazio)")
        return {"error": "model_not_configured", "error_message": "IA_MODEL não está configurado"}
    
    log.info("Usando modelo Kilo AI: %s", model)
    
    for attempt in range(len(timeouts)):
        try:
            client = _get_kilo_client()
            timeout = timeouts[attempt]
            
            log.info("Tentativa %d/%d - Enviando requisição para Kilo AI", attempt + 1, len(timeouts))
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
                "Kilo AI resposta recebida (%d chars): %.400s",
                len(txt), txt,
            )

            if not txt:
                log.warning("Kilo AI retornou resposta vazia.")
                if attempt == 0:
                    continue
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
            log.warning("JSON do Kilo AI inválido (tentativa %d/%d): %s - Resposta: %.200s", attempt + 1, len(timeouts), exc, txt[:200] if 'txt' in locals() else "N/A")
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "json_decode", "error_message": str(exc), "raw_response": raw_response[:500]}
        except asyncio.TimeoutError as exc:
            last_error = exc
            log.warning("Timeout do Kilo AI (tentativa %d/%d, timeout=%.1fs)", attempt + 1, len(timeouts), timeouts[attempt])
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "timeout", "error_message": str(exc)}
        except Exception as exc:
            last_error = exc
            log.error("Análise por Kilo AI falhou (tentativa %d/%d): %s - Tipo: %s - Detalhes: %s", attempt + 1, len(timeouts), str(exc), type(exc).__name__, str(exc.__dict__) if hasattr(exc, '__dict__') else "")
            if attempt < len(timeouts) - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            return {"error": "exception", "error_message": str(exc), "error_type": type(exc).__name__}

    if last_error:
        log.error("Análise por Kilo AI esgotou tentativas: %s", last_error)
    return {"error": "exhausted_retries", "last_error": str(last_error) if last_error else "unknown"}
