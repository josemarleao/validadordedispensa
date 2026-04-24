"""Ponto de entrada da API – Saneamento de DL via PDF (MPBA)."""

import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.saneamento import router as saneamento_router
from config import settings
from middleware.rate_limiter import FreeTierLimiter, get_usage_status, rate_limit_exceeded_handler

logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# Configurar rate limiter
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="MPBA - Saneamento de Dispensa de Licitação (PDF)",
    description="",
    version="1.0.0",
    contact={"name": "Assessoria de Contratações - MPBA"},
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Adicionar middleware de rate limiting do free tier
free_tier_limiter = FreeTierLimiter()
app.middleware("http")(free_tier_limiter)

# CORS – permite chamadas do Azure Static Web Apps, Power Pages e de qualquer origem local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://*.azurestaticapps.net",   # Azure Static Web Apps
        "https://*.azurecontainerapps.io", # Azure Container Apps
        "https://*.powerappsportals.com",  # Power Pages
        "https://validadordedispensa.powerappsportals.com", # Power Pages específico
        "https://org9a615910.crm2.dynamics.com", # Dynamics CRM específico
        "https://validadordedispensa.crm2.dynamics.com", # Dynamics CRM específico
        "http://localhost",
        "http://localhost:3000",
        "http://127.0.0.1",
    ],
    allow_origin_regex=r"https://.*\.(azurestaticapps\.net|azurecontainerapps\.io|powerappsportals\.com)",
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(saneamento_router)


@app.get("/")
async def health_check():
    return {"status": "ok", "message": "API de Saneamento de DL via PDF está funcionando"}


@app.get("/usage")
async def usage_stats():
    """Retorna estatísticas de uso do tier gratuito."""
    return get_usage_status()


@app.get("/docs", include_in_schema=False)
async def swagger_ui():
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.responses import HTMLResponse
    html = get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title,
        swagger_ui_parameters=app.swagger_ui_parameters,
    )
    body = html.body.decode()
    body = body.replace(
        "</style>",
        ".download-url-wrapper { display: none !important; }</style>",
    )
    return HTMLResponse(body)


def _custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path in schema.get("paths", {}).values():
        for method in path.values():
            method.get("responses", {}).pop("422", None)
    app.openapi_schema = schema
    return schema

app.openapi = _custom_openapi


def _downgrade_openapi_30(schema: dict) -> dict:
    """Converte schema OpenAPI 3.1 → 3.0.3 para compatibilidade com Power Apps."""
    import copy

    def _fix(obj: object) -> None:
        """Substitui anyOf:[{...},{type:null}] por {nullable:true,...} recursivamente."""
        if isinstance(obj, dict):
            if "anyOf" in obj:
                non_null = [x for x in obj["anyOf"] if x != {"type": "null"}]
                has_null = len(non_null) < len(obj["anyOf"])
                if has_null and len(non_null) == 1:
                    obj.update(non_null[0])
                    obj["nullable"] = True
                    del obj["anyOf"]
            for v in list(obj.values()):
                _fix(v)
        elif isinstance(obj, list):
            for item in obj:
                _fix(item)

    s = copy.deepcopy(schema)
    s["openapi"] = "3.0.3"
    s.get("info", {}).pop("jsonSchemaDialect", None)
    _fix(s)
    return s


@app.get("/openapi-powerapps.json", include_in_schema=False)
def openapi_powerapps():
    from fastapi.responses import JSONResponse
    return JSONResponse(_downgrade_openapi_30(app.openapi()))


@app.exception_handler(Exception)
async def handler_generico(request, exc):
    log.error("Erro não tratado: %s", exc, exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Erro interno do servidor."})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
