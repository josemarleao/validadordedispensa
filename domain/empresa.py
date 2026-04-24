"""Modelos e extratores de documentos da empresa."""

from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel
from .base import validar_cnpj


class EmpresaExtraida(BaseModel):
    razao_social: Optional[str] = None
    cnpj: Optional[str] = None
    cnpj_valido: bool = False
    cnae_principal: Optional[str] = None
    sicaf_presente: bool = False
    comprovante_banco: Optional[str] = None
    comprovante_agencia: Optional[str] = None
    comprovante_conta: Optional[str] = None
    comprovante_contem_extrato: bool = False
    declaracao_nao_emprega_menor: bool = False
    declaracao_cnmp_presente: bool = False
    menciona_cnmp_37_2009: bool = False
    menciona_cnj_07_2005: bool = False


def extrair_empresa(texto: str) -> EmpresaExtraida:
    def buscar(pattern: str) -> Optional[str]:
        m = re.search(pattern, texto, re.IGNORECASE)
        return m.group(1).strip() if m else None

    cnpj_raw = buscar(r"cnpj\s*[:\-]?\s*([\d.\/\-]+)")
    return EmpresaExtraida(
        razao_social=buscar(r"raz[aã]o\s+social\s*[:\-]?\s*([^\n]+)"),
        cnpj=cnpj_raw,
        cnpj_valido=validar_cnpj(cnpj_raw or ""),
        cnae_principal=buscar(r"cnae\s+principal\s*[:\-]?\s*([^\n]+)"),
        sicaf_presente=bool(re.search(r"sicaf", texto, re.IGNORECASE)),
        comprovante_banco=buscar(r"banco\s*[:\-]?\s*([^\n]+)"),
        comprovante_agencia=buscar(r"ag[eê]ncia\s*[:\-]?\s*([\d\-]+)"),
        comprovante_conta=buscar(r"conta\s*corrente\s*[:\-]?\s*([\d\-]+)"),
        comprovante_contem_extrato=bool(
            re.search(r"saldo|extrato\s+banc", texto, re.IGNORECASE)
        ),
        declaracao_nao_emprega_menor=bool(
            re.search(
                r"menor\s+de\s+\d+"         # "menor de 18/16/14 anos"
                r"|menor\s+de\s+idade"       # "menor de idade" (título alternativo)
                r"|n[aã]o\s+emprega\s+menor" # "não emprega menor"
                r"|art[.\s]+7.*constitui",   # "art. 7º ... Constituição"
                texto, re.IGNORECASE,
            )
        ),
        declaracao_cnmp_presente=bool(re.search(r"cnmp|resolucao.*cnmp", texto, re.IGNORECASE)),
        menciona_cnmp_37_2009=bool(re.search(r"cnmp.*37/2009|37/2009.*cnmp", texto, re.IGNORECASE)),
        menciona_cnj_07_2005=bool(re.search(r"cnj.*07/2005|07/2005.*cnj", texto, re.IGNORECASE)),
    )
