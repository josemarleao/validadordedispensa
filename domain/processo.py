"""Agregador do processo – monta o objeto Processo a partir dos segmentos extraídos."""

from __future__ import annotations
import logging
import re
from typing import Optional
from pydantic import BaseModel

from .dfd import DFDExtraido, extrair_dfd
from .tr_unificado import TRUnificado, TRServicosExtraido, TRAquisicoesExtraido, extrair_tr
from .tabela_precos import TabelaPrecosExtraida, extrair_tabela_precos
from .orcamentos import OrcamentoExtraido, extrair_orcamento
from .certidoes import CertidoesExtraidas, extrair_certidoes
from .empresa import EmpresaExtraida, extrair_empresa
from .executor import ExecutorExtraido, MemoriaCalculoExtraida, FIPLANExtraido
from .executor import extrair_executor, extrair_memoria_calculo, extrair_fiplan
from .gestor import GestorExtraido, CienciaExtraida, extrair_gestor, extrair_ciencias
from pdf.classifier import DocumentoExtraido

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Divisão de segmento ORCAMENTO com múltiplos orçamentos
# ─────────────────────────────────────────────────────────────────────────────

# Padrões que indicam o INÍCIO de um novo orçamento/proposta numa página.
# Presença de qualquer desses no início (~800 chars) da página = nova proposta.
_INICIO_ORC = re.compile(
    r"(?:proposta\s+(?:comercial|de\s+pre[cç]os?)|modelo\s+de\s+proposta"
    r"|cotac[aã]o\s+de\s+pre[cç]os?|empresa\s+proponente"
    r"|dados\s+do\s+fornecedor"
    r"|raz[aã]o\s+social\s*[:\-]?"          # separador opcional
    r"|cnpj\s*[:\-/]?\s*\d{2}"             # CNPJ seguido de dígitos (sem separador)
    r"|\bor[cç]amento\s+(?:n[°º]\.?\s*)?\d" # "Orçamento 1" / "Orçamento nº 2"
    r"|fornecedor\s*[:\-])",
    re.IGNORECASE,
)


def _dividir_orcamentos(textos_paginas: list[str]) -> list[str]:
    """Agrupa páginas em orçamentos individuais.

    Cada página que contém um cabeçalho de novo orçamento (Proposta Comercial,
    CNPJ, Razão Social, etc.) inicia um novo grupo. Páginas sem cabeçalho são
    continuação do orçamento anterior (orçamentos de múltiplas páginas).

    Recebe a lista de textos individuais por página (não o texto_completo fundido).
    Se a lista tiver só uma página, retorna essa página diretamente.
    """
    if len(textos_paginas) <= 1:
        return textos_paginas or [""]

    grupos: list[list[str]] = []
    for texto_pag in textos_paginas:
        cabecalho = texto_pag[:800]
        if _INICIO_ORC.search(cabecalho) or not grupos:
            grupos.append([texto_pag])
        else:
            # Continuação do orçamento anterior
            grupos[-1].append(texto_pag)

    return ["\n".join(g) for g in grupos if any(p.strip() for p in g)]


class ProcessoExtraido(BaseModel):
    numero_sei: str
    unidade_demandante: Optional[str] = None

    dfd: Optional[DFDExtraido] = None
    tr: Optional[TRUnificado] = None
    tabela_precos: Optional[TabelaPrecosExtraida] = None
    orcamentos: list[OrcamentoExtraido] = []
    certidoes: Optional[CertidoesExtraidas] = None
    empresa: Optional[EmpresaExtraida] = None
    executor: Optional[ExecutorExtraido] = None
    memoria_calculo: Optional[MemoriaCalculoExtraida] = None
    fiplan: Optional[FIPLANExtraido] = None
    gestor: Optional[GestorExtraido] = None
    ciencias: list[CienciaExtraida] = []

    documentos_encontrados: list[str] = []
    paginas_processadas: int = 0
    ocr_utilizado: bool = False


def montar_processo(
    segmentos: list[DocumentoExtraido],
    numero_sei: str,
    unidade_demandante: str = "",
    total_paginas: int = 0,
) -> ProcessoExtraido:
    """Mapeia cada segmento classificado para o modelo de domínio correspondente."""

    processo = ProcessoExtraido(
        numero_sei=numero_sei,
        unidade_demandante=unidade_demandante,
        # Usa total_paginas (todas extraídas do PDF) quando disponível; fallback
        # para a soma dos segmentos classificados (deve ser igual após absorção).
        paginas_processadas=total_paginas or sum(len(s.paginas) for s in segmentos),
    )

    for seg in segmentos:
        tipo = seg.tipo
        txt  = seg.texto_completo
        log.debug("Extraindo segmento '%s' (%d págs, conf=%.2f)", tipo, len(seg.paginas), seg.confianca)

        try:
            if tipo == "DFD":
                processo.dfd = extrair_dfd(txt, seg.textos_paginas or [txt])
                processo.documentos_encontrados.append("DFD")

            elif tipo in ("TR_SERVICOS", "TR_AQUISICOES"):
                processo.tr = extrair_tr(txt, tipo, seg.textos_paginas or [txt])
                processo.documentos_encontrados.append(tipo)

            elif tipo == "TABELA_PRECOS":
                processo.tabela_precos = extrair_tabela_precos(txt, seg.textos_paginas or [txt])
                processo.documentos_encontrados.append("TABELA_PRECOS")

            elif tipo == "ORCAMENTO":
                for orc_txt in _dividir_orcamentos(seg.textos_paginas or [txt]):
                    processo.orcamentos.append(extrair_orcamento(orc_txt))
                if "ORCAMENTO" not in processo.documentos_encontrados:
                    processo.documentos_encontrados.append("ORCAMENTO")

            elif tipo == "CERTIDAO":
                if processo.certidoes is None:
                    processo.certidoes = CertidoesExtraidas()
                cert = extrair_certidoes(txt)
                # Mescla: mantém a certidão presente mais recente
                for campo in ["federal_divida_ativa", "estadual", "municipal", "cndt", "fgts_crf"]:
                    existente = getattr(processo.certidoes, campo)
                    nova = getattr(cert, campo)
                    from .base import StatusCertidao
                    if nova.status != StatusCertidao.AUSENTE:
                        setattr(processo.certidoes, campo, nova)
                if "CERTIDAO" not in processo.documentos_encontrados:
                    processo.documentos_encontrados.append("CERTIDAO")

            elif tipo in ("CARTAO_CNPJ", "CONTRATO_SOCIAL", "DECLARACAO", "COMPROVANTE_BANCARIO"):
                if processo.empresa is None:
                    processo.empresa = extrair_empresa(txt)
                else:
                    # Complementa campos ausentes
                    nova = extrair_empresa(txt)
                    for campo in nova.model_fields:
                        if getattr(processo.empresa, campo) in (None, False):
                            setattr(processo.empresa, campo, getattr(nova, campo))
                if tipo not in processo.documentos_encontrados:
                    processo.documentos_encontrados.append(tipo)

            elif tipo == "SICAF":
                if processo.empresa is None:
                    processo.empresa = EmpresaExtraida(sicaf_presente=True)
                else:
                    processo.empresa.sicaf_presente = True
                processo.documentos_encontrados.append("SICAF")

            elif tipo == "EXECUTOR_ORCAMENTARIO":
                processo.executor = extrair_executor(txt)
                processo.documentos_encontrados.append("EXECUTOR_ORCAMENTARIO")

            elif tipo == "MEMORIA_CALCULO":
                processo.memoria_calculo = extrair_memoria_calculo(txt)
                processo.documentos_encontrados.append("MEMORIA_CALCULO")

            elif tipo == "DEMONSTRATIVO_FIPLAN":
                processo.fiplan = extrair_fiplan(txt)
                processo.documentos_encontrados.append("DEMONSTRATIVO_FIPLAN")

            elif tipo == "MANIFESTACAO_GESTOR":
                processo.gestor = extrair_gestor(txt)
                processo.documentos_encontrados.append("MANIFESTACAO_GESTOR")

            elif tipo == "MANIFESTACAO_CIENCIA":
                processo.ciencias.extend(extrair_ciencias(txt))
                if "MANIFESTACAO_CIENCIA" not in processo.documentos_encontrados:
                    processo.documentos_encontrados.append("MANIFESTACAO_CIENCIA")

        except Exception as exc:
            log.warning("Falha ao extrair segmento '%s': %s", tipo, exc)

    return processo
