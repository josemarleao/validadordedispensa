"""Rate limiting middleware para Azure Container Apps free tier."""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict

from fastapi import HTTPException, Request, Response
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

log = logging.getLogger(__name__)

# Configurações dos limites gratuitos do Azure Container Apps
FREE_TIER_LIMITS = {
    "cpu_seconds_per_month": 180_000,  # 180,000 vCPU-segundos
    "gib_seconds_per_month": 360_000,  # 360,000 GiB-segundos
    "requests_per_month": 2_000_000,    # 2,000,000 requisições
}

# Estimativa de recursos por análise (com CPU=4 vCPU, RAM=8 GiB, tempo=40s otimizado)
RESOURCES_PER_ANALYSIS = {
    "cpu_seconds": 160,     # 4 vCPU × 40 segundos (com overhead de paralelismo)
    "gib_seconds": 320,     # 8 GiB × 40 segundos (com overhead de paralelismo)
    "requests": 1,
}

# Limites diários seguros (80% do mensal para margem de segurança)
DAILY_LIMITS = {
    "cpu_seconds": FREE_TIER_LIMITS["cpu_seconds_per_month"] * 0.8 / 30,    # 4,800 vCPU-segundos
    "gib_seconds": FREE_TIER_LIMITS["gib_seconds_per_month"] * 0.8 / 30,    # 9,600 GiB-segundos
    "requests": FREE_TIER_LIMITS["requests_per_month"] * 0.8 / 30,        # 53,333 requisições
}

# Storage em memória para contadores (em produção, usar Redis)
usage_counters: Dict[str, Dict] = {}


def get_date_key() -> str:
    """Retorna chave para data atual."""
    return datetime.now().strftime("%Y-%m-%d")


def get_usage_data(date_key: str) -> Dict:
    """Retorna dados de uso para uma data."""
    if date_key not in usage_counters:
        usage_counters[date_key] = {
            "cpu_seconds": 0,
            "gib_seconds": 0,
            "requests": 0,
            "analyses": 0,
            "last_reset": datetime.now().isoformat()
        }
    return usage_counters[date_key]


def check_limits() -> bool:
    """Verifica se ainda dentro dos limites diários."""
    date_key = get_date_key()
    usage = get_usage_data(date_key)
    
    return (
        usage["cpu_seconds"] < DAILY_LIMITS["cpu_seconds"] and
        usage["gib_seconds"] < DAILY_LIMITS["gib_seconds"] and
        usage["requests"] < DAILY_LIMITS["requests"]
    )


def record_usage():
    """Registra uso de recursos."""
    date_key = get_date_key()
    usage = get_usage_data(date_key)
    
    usage["cpu_seconds"] += RESOURCES_PER_ANALYSIS["cpu_seconds"]
    usage["gib_seconds"] += RESOURCES_PER_ANALYSIS["gib_seconds"]
    usage["requests"] += RESOURCES_PER_ANALYSIS["requests"]
    usage["analyses"] += 1


def get_usage_status() -> Dict:
    """Retorna status atual do uso."""
    date_key = get_date_key()
    usage = get_usage_data(date_key)
    
    return {
        "date": date_key,
        "usage": {
            "cpu_seconds": usage["cpu_seconds"],
            "cpu_limit": DAILY_LIMITS["cpu_seconds"],
            "cpu_percent": (usage["cpu_seconds"] / DAILY_LIMITS["cpu_seconds"]) * 100,
            "gib_seconds": usage["gib_seconds"],
            "gib_limit": DAILY_LIMITS["gib_seconds"],
            "gib_percent": (usage["gib_seconds"] / DAILY_LIMITS["gib_seconds"]) * 100,
            "requests": usage["requests"],
            "requests_limit": DAILY_LIMITS["requests"],
            "requests_percent": (usage["requests"] / DAILY_LIMITS["requests"]) * 100,
            "analyses": usage["analyses"],
            "remaining_analyses": min(
                int((DAILY_LIMITS["cpu_seconds"] - usage["cpu_seconds"]) / RESOURCES_PER_ANALYSIS["cpu_seconds"]),
                int((DAILY_LIMITS["gib_seconds"] - usage["gib_seconds"]) / RESOURCES_PER_ANALYSIS["gib_seconds"]),
                int((DAILY_LIMITS["requests"] - usage["requests"]) / RESOURCES_PER_ANALYSIS["requests"])
            )
        },
        "within_limits": check_limits()
    }


class FreeTierLimiter:
    """Middleware para limitar uso ao tier gratuito do Azure."""
    
    def __init__(self):
        self.name = "free_tier_limiter"
    
    async def __call__(self, request: Request, call_next):
        # Verificar se é endpoint de análise
        if "/saneamento/processo" in request.url.path and request.method == "POST":
            # Verificar limites antes de processar
            if not check_limits():
                usage_status = get_usage_status()
                log.warning(f"Limites do free tier excedidos: {usage_status}")
                
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "RATE_LIMIT_EXCEEDED",
                        "message": "Limites diários do plano gratuito excedidos. Tente novamente amanhã.",
                        "usage": usage_status,
                        "retry_after": "tomorrow"
                    }
                )
            
            # Registrar uso antes de processar
            record_usage()
        
        # Processar request
        response = await call_next(request)
        
        # Adicionar headers de uso nos responses
        if "/saneamento/processo" in request.url.path:
            usage_status = get_usage_status()
            response.headers["X-Usage-Percent"] = f"{usage_status['usage']['cpu_percent']:.1f}%"
            response.headers["X-Remaining-Analyses"] = str(usage_status['usage']['remaining_analyses'])
        
        return response


# Limiter padrão para proteção adicional
limiter = Limiter(key_func=get_remote_address)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Handler customizado para rate limit exceeded."""
    usage_status = get_usage_status()
    
    return JSONResponse(
        status_code=429,
        content={
            "error": "RATE_LIMIT_EXCEEDED",
            "message": "Muitas requisições. Por favor, aguarde.",
            "usage": usage_status,
            "retry_after": str(exc.retry_after)
        }
    )
