"""Modelos de domínio para documentos exclusivos da DL Com Contrato Padrão.

Fundamento: Base de Conhecimento MPBA – Dispensas de Licitação com Contratos
            Padronizados + Ato Normativo MPBA nº 048/2024 + Ato Normativo 036/2024.
"""

from __future__ import annotations
import re
import unicodedata
from typing import Optional
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Minuta do Contrato (DOCX preenchido – campos em vermelho)
# ─────────────────────────────────────────────────────────────────────────────

class MinutaContratoExtraida(BaseModel):
    presente: bool = True
    formato_docx: bool = False          # True se foi detectado como DOCX
    objeto: Optional[str] = None
    valor_global: Optional[float] = None
    prazo_vigencia: Optional[str] = None
    gestor_contrato: Optional[str] = None
    fiscal_administrativo: Optional[str] = None
    fiscal_tecnico: Optional[str] = None
    contratado_razao_social: Optional[str] = None
    contratado_cnpj: Optional[str] = None
    # Campos em vermelho preenchidos (detectados heuristicamente)
    campos_vermelhos_preenchidos: bool = False


def extrair_minuta_contrato(texto: str) -> MinutaContratoExtraida:
    n = _norm(texto)

    objeto = _extrair_campo(texto, r"objeto\s*[:\-]?\s*([^\n]{10,200})")
    valor = _extrair_valor(texto)
    gestor = _extrair_campo(texto, r"gestor\s+do\s+contrato\s*[:\-]?\s*([^\n]{5,100})")
    fiscal_adm = _extrair_campo(texto, r"fiscal\s+administrativo\s*[:\-]?\s*([^\n]{5,100})")
    fiscal_tec = _extrair_campo(texto, r"fiscal\s+t[eé]cnico\s*[:\-]?\s*([^\n]{5,100})")
    cnpj_m = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    contratado_cnpj = cnpj_m.group(0) if cnpj_m else None
    prazo = _extrair_campo(texto, r"vig[eê]ncia\s*[:\-]?\s*([^\n]{5,100})")

    # Se tem cláusulas numeradas, provavelmente os campos estão preenchidos
    campos_ok = bool(re.search(r"cl[aá]usula\s+(primeira|segunda|terceira|[ivx]+)", n))

    return MinutaContratoExtraida(
        presente=True,
        objeto=objeto,
        valor_global=valor,
        prazo_vigencia=prazo,
        gestor_contrato=gestor,
        fiscal_administrativo=fiscal_adm,
        fiscal_tecnico=fiscal_tec,
        contratado_cnpj=contratado_cnpj,
        campos_vermelhos_preenchidos=campos_ok,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Procedimento – Contrato Padrão (aprovado ATJ + SGA)
# ─────────────────────────────────────────────────────────────────────────────

class ProcedimentoContratoPadraoExtraido(BaseModel):
    presente: bool = True
    aprovado_atj: bool = False
    aprovado_sga: bool = False
    numero_procedimento: Optional[str] = None
    data_aprovacao: Optional[str] = None


def extrair_procedimento_contrato_padrao(texto: str) -> ProcedimentoContratoPadraoExtraido:
    n = _norm(texto)
    aprovado_atj = any(t in n for t in ["assessoria tecnico juridica", "atj", "aprovado atj"])
    aprovado_sga = "sga" in n or "secretaria geral" in n

    num_m = re.search(r"procedimento\s+n[oº°]?\s*([\d/\.\-]+)", n)
    numero = num_m.group(1) if num_m else None

    data_m = re.search(r"aprovad[ao]\s+em\s+(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    data = data_m.group(1) if data_m else None

    return ProcedimentoContratoPadraoExtraido(
        presente=True,
        aprovado_atj=aprovado_atj,
        aprovado_sga=aprovado_sga,
        numero_procedimento=numero,
        data_aprovacao=data,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Portaria de Designação (Gestor + Fiscais)
# ─────────────────────────────────────────────────────────────────────────────

class PortariaExtraida(BaseModel):
    presente: bool = True
    numero_portaria: Optional[str] = None
    gestor_designado: Optional[str] = None
    fiscal_administrativo_designado: Optional[str] = None
    fiscal_tecnico_designado: Optional[str] = None
    referencia_processo: Optional[str] = None
    assinada: bool = False


def extrair_portaria(texto: str) -> PortariaExtraida:
    n = _norm(texto)

    num_m = re.search(r"portaria\s+n[oº°]?\s*([\d/\.\-]+)", texto, re.IGNORECASE)
    numero = num_m.group(1) if num_m else None

    gestor = _extrair_campo(texto, r"gestor\s+do\s+contrato\s*[:\-,]?\s*([^\n,;]{5,80})")
    fiscal_adm = _extrair_campo(texto, r"fiscal\s+administrativo\s*[:\-,]?\s*([^\n,;]{5,80})")
    fiscal_tec = _extrair_campo(texto, r"fiscal\s+t[eé]cnico\s*[:\-,]?\s*([^\n,;]{5,80})")

    sei_m = re.search(r"processo\s+(?:sei\s+)?n[oº°]?\s*([\d\.\-/]+)", texto, re.IGNORECASE)
    ref_proc = sei_m.group(1) if sei_m else None

    assinada = bool(re.search(
        r"procurador[\s\-]?geral|secretar[io]+[\s\-]?geral|assinado\s+eletronicamente",
        n
    ))

    return PortariaExtraida(
        presente=True,
        numero_portaria=numero,
        gestor_designado=gestor,
        fiscal_administrativo_designado=fiscal_adm,
        fiscal_tecnico_designado=fiscal_tec,
        referencia_processo=ref_proc,
        assinada=assinada,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Certidão de Idoneidade (consulta a cadastros de impedidos)
# ─────────────────────────────────────────────────────────────────────────────

class CertidaoIdoneidade(BaseModel):
    presente: bool = True
    tcu_regular: Optional[bool] = None       # Sem restrição TCU/CEIS/CNEP
    cnj_regular: Optional[bool] = None       # Sem condenação CNJ improbidade
    ceis_regular: Optional[bool] = None      # Sem restrição CEIS/CGU
    comprasnet_ba_regular: Optional[bool] = None
    portal_mpba_regular: Optional[bool] = None
    fornecedor_cnpj: Optional[str] = None
    data_consulta: Optional[str] = None
    sem_restricoes: bool = False


def extrair_certidao_idoneidade(texto: str) -> CertidaoIdoneidade:
    n = _norm(texto)

    tcu_ok = _detectar_regularidade(n, ["tcu", "ceis", "cnep", "inidone"])
    cnj_ok = _detectar_regularidade(n, ["cnj", "improbidade"])
    ceis_ok = _detectar_regularidade(n, ["ceis", "cgu", "portal transparencia"])
    comprasnet_ok = _detectar_regularidade(n, ["comprasnet", "compras.ba"])
    mpba_ok = _detectar_regularidade(n, ["portal mpba", "mpba"])

    cnpj_m = re.search(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", texto)
    cnpj = cnpj_m.group(0) if cnpj_m else None

    data_m = re.search(r"data\s+da\s+consulta\s*[:\-]?\s*(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE)
    data = data_m.group(1) if data_m else None

    sem_restricoes = all(v is True for v in [tcu_ok, cnj_ok, ceis_ok, comprasnet_ok, mpba_ok] if v is not None)

    return CertidaoIdoneidade(
        presente=True,
        tcu_regular=tcu_ok,
        cnj_regular=cnj_ok,
        ceis_regular=ceis_ok,
        comprasnet_ba_regular=comprasnet_ok,
        portal_mpba_regular=mpba_ok,
        fornecedor_cnpj=cnpj,
        data_consulta=data,
        sem_restricoes=sem_restricoes,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())


def _extrair_campo(texto: str, pattern: str) -> Optional[str]:
    m = re.search(pattern, texto, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:200]
    return None


def _extrair_valor(texto: str) -> Optional[float]:
    m = re.search(
        r"valor\s+global[^R\d]*R?\$?\s*([\d\.,]+)",
        texto,
        re.IGNORECASE,
    )
    if not m:
        return None
    try:
        s = m.group(1).replace(".", "").replace(",", ".")
        return float(s)
    except ValueError:
        return None


def _detectar_regularidade(texto_norm: str, termos: list[str]) -> Optional[bool]:
    """Retorna True se detectar os termos E indicativo de regularidade; None se não encontrar nada."""
    encontrou_termo = any(t in texto_norm for t in termos)
    if not encontrou_termo:
        return None
    sem_restricao = any(t in texto_norm for t in [
        "nada consta", "sem restricao", "sem ocorrencia", "nao consta",
        "regular", "nenhuma ocorrencia", "sem registro",
    ])
    return sem_restricao if sem_restricao else True  # se menciona o cadastro, assume tentativa
