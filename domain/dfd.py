"""Modelo do DFD extraído do PDF."""

from __future__ import annotations
import re
from typing import Optional
from pydantic import BaseModel
from .base import normalizar


class DFDExtraido(BaseModel):
    """Campos do DFD conforme modelo oficial MPBA."""
    primeiro_documento: bool = True
    objeto: Optional[str] = None
    tic: Optional[str] = None                    # "SIM" | "NÃO"
    unidade_solicitante: Optional[str] = None
    unidade_gestora: Optional[str] = None        # formato: XX.XXX – Nome
    origem_convenio: Optional[str] = None        # "SIM" | "NÃO"
    nome_concedente: Optional[str] = None
    numero_convenio: Optional[str] = None
    pca: Optional[str] = None                    # "SIM" | "NÃO"
    pca_item: Optional[str] = None
    pca_codigo: Optional[str] = None
    pca_valor_estimado: Optional[float] = None
    pca_justificativa: Optional[str] = None
    despacho_sga_presente: bool = False
    responsavel_nome: Optional[str] = None
    responsavel_unidade: Optional[str] = None
    responsavel_assinatura_nome: Optional[str] = None
    superior_nome: Optional[str] = None
    superior_orgao: Optional[str] = None
    superior_assinou: bool = False
    superior_ciencia: bool = False
    blocos_texto: list[str] = []
    # Texto bruto do documento – preservado para análise por IA
    texto_original: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Extrator heurístico de campos do DFD
# ─────────────────────────────────────────────────────────────────────────────

def extrair_dfd(texto: str, blocos_texto: Optional[list[str]] = None) -> DFDExtraido:
    """Extrai campos do DFD a partir do texto bruto da página."""
    t = texto

    def buscar(pattern: str) -> Optional[str]:
        m = re.search(pattern, t, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    objeto = buscar(
        r"objeto\s+da\s+futura\s+contrata[çc][aã]o\s*[:\-]?\s*([^\n]+(?:\n(?!\d+\.).*)*)"
    )
    if objeto:
        objeto = re.sub(r"\s+", " ", objeto).strip()

    unidade_solicitante = buscar(r"unidade\s+solicitante\s*[:\-]?\s*([^\n]+)")
    # O modelo DFD MPBA coloca "(Código e Nome):" na mesma linha do rótulo
    # e o valor real na linha seguinte (ex: "40.101 - 0049/PJR Irecê").
    # Tenta capturar na mesma linha; se o resultado for só um label descartável,
    # captura a linha seguinte.
    unidade_gestora = buscar(r"unidade\s+gestora\s+do\s+recurso[^\n]*\n\s*(\d+[^\n]+)")
    if not unidade_gestora:
        unidade_gestora = buscar(r"unidade\s+gestora\s+do\s+recurso\s*[:\-]\s*([^\n]{5,})")
    responsavel_nome    = buscar(r"respons[aá]vel\s+pelo\s+preenchimento\s*[:\-]?\s*([^\n]+)")
    superior_nome       = buscar(r"superior\s+imediato\s*[:\-]?\s*([^\n]+)")


    # TIC: modelo DFD MPBA coloca a pergunta em uma linha e os checkboxes na próxima
    # Ex: "Tecnologia da Informação e Comunicação (TIC)?\n   ( ) SIM   (X) NÃO"
    _CHECKBOX_DFD = r"(?:\(\s*[xX✓]\s*\)|\[\s*[xX✓]\s*\]|☑|✓)"
    tic = None
    m_tic = re.search(r"(?:tic\b|tecnologia\s+da\s+informa)[^\n]*(?:\n[^\n]*){0,3}", t, re.IGNORECASE)
    if m_tic:
        bloco_tic = m_tic.group(0)
        if re.search(_CHECKBOX_DFD + r"\s*n[aã]o|n[aã]o\s*" + _CHECKBOX_DFD, bloco_tic, re.IGNORECASE):
            tic = "NÃO"
        elif re.search(_CHECKBOX_DFD + r"\s*sim|sim\s*" + _CHECKBOX_DFD, bloco_tic, re.IGNORECASE):
            tic = "SIM"

    pca = None
    if re.search(r"pca\s*[:\-]?\s*\[?x\]?\s*sim", t, re.IGNORECASE):
        pca = "SIM"
    elif re.search(r"pca\s*[:\-]?\s*\[?x\]?\s*n[aã]o", t, re.IGNORECASE):
        pca = "NÃO"

    pca_justificativa = None
    if pca == "NÃO":
        pca_justificativa = buscar(
            r"justificativa.*?n[aã]o\s+previs[aã]o.*?pca\s*[:\-]?\s*([^\n]+)"
        )

    origem_convenio = None
    if re.search(r"conv[eê]nio\s*[:\-]?\s*\[?x\]?\s*sim", t, re.IGNORECASE):
        origem_convenio = "SIM"
    elif re.search(r"conv[eê]nio\s*[:\-]?\s*\[?x\]?\s*n[aã]o", t, re.IGNORECASE):
        origem_convenio = "NÃO"

    superior_assinou = bool(
        re.search(r"superior.*?assinou|assinado.*?superior", t, re.IGNORECASE)
    )
    superior_ciencia = bool(
        re.search(r"ciente|ci[eê]ncia|despacho\s+de\s+ci[eê]ncia", t, re.IGNORECASE)
    )

    return DFDExtraido(
        objeto=objeto,
        tic=tic,
        unidade_solicitante=unidade_solicitante,
        unidade_gestora=unidade_gestora,
        origem_convenio=origem_convenio,
        pca=pca,
        pca_justificativa=pca_justificativa,
        responsavel_nome=responsavel_nome,
        responsavel_assinatura_nome=responsavel_nome,  # mesmo campo na extração
        superior_nome=superior_nome,
        superior_assinou=superior_assinou,
        superior_ciencia=superior_ciencia,
        blocos_texto=blocos_texto or [texto],
        texto_original=texto,
    )
