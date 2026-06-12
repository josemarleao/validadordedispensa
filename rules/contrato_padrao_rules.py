"""Regras normativas exclusivas da DL com Contrato Padrão.

Fundamento: Base de Conhecimento MPBA – Dispensas de Licitação com Contratos
            Padronizados + Ato Normativo MPBA nº 048/2024 + Ato Normativo 036/2024
            art. 18 §1º + Lei 14.133/2021 art. 117.
"""

from __future__ import annotations
import re
import unicodedata
import logging
from domain.processo import ProcessoExtraido
from knowledge_base.normas import (
    NORMAS_CONTRATO_PADRAO,
    REGRAS_CERTIDAO_IDONEIDADE,
    REGRAS_MINUTA_CONTRATO,
    REGRAS_PORTARIA_DESIGNACAO,
    REGRAS_USUARIO_EXTERNO_SEI,
)
from schemas.responses import ResultadoItem, StatusRegra, Providencia

log = logging.getLogger(__name__)

_DOC_PROC  = "Procedimento – Contrato Padrão"
_DOC_MIN   = "Minuta do Contrato"
_DOC_PORT  = "Portaria de Designação"
_DOC_IDAD  = "Certidão de Idoneidade"


def aplicar_regras_contrato_padrao(processo: ProcessoExtraido) -> list[ResultadoItem]:
    """Aplica todas as regras exclusivas da DL com Contrato Padrão.

    Retorna lista vazia se o processo não for do tipo 'com_contrato_padrao'.
    """
    if processo.tipo_processo != "com_contrato_padrao":
        return []

    resultados: list[ResultadoItem] = []
    resultados += _regras_procedimento(processo)
    resultados += _regras_minuta(processo)
    resultados += _regras_portaria(processo)
    resultados += _regras_certidao_idoneidade(processo)
    resultados += _regras_objeto_especifico(processo)
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Procedimento – Contrato Padrão
# ─────────────────────────────────────────────────────────────────────────────

def _regras_procedimento(processo: ProcessoExtraido) -> list[ResultadoItem]:
    resultados: list[ResultadoItem] = []
    proc = processo.procedimento_contrato_padrao

    if proc is None:
        resultados.append(_inconforme(
            _DOC_PROC,
            "Procedimento – Contrato Padrão",
            "Documento não localizado no processo. "
            "Para DL com Contrato Padrão, o Procedimento aprovado pela ATJ e SGA "
            "é obrigatório (Ato Normativo MPBA nº 048/2024).",
            Providencia.CORRIGIR,
        ))
        return resultados

    if not proc.aprovado_atj:
        resultados.append(_inconforme(
            _DOC_PROC,
            "Aprovação ATJ",
            "Não foi possível confirmar aprovação pela Assessoria Técnico-Jurídica (ATJ). "
            "Verificar se o Procedimento é o modelo vigente aprovado.",
        ))
    else:
        resultados.append(_conforme(_DOC_PROC, "Aprovação ATJ", "Aprovação ATJ identificada ✓"))

    if not proc.aprovado_sga:
        resultados.append(_inconforme(
            _DOC_PROC,
            "Aprovação SGA",
            "Não foi possível confirmar aprovação pela SGA. "
            "Verificar se o Procedimento é o modelo vigente aprovado.",
        ))
    else:
        resultados.append(_conforme(_DOC_PROC, "Aprovação SGA", "Aprovação SGA identificada ✓"))

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Minuta do Contrato
# ─────────────────────────────────────────────────────────────────────────────

def _regras_minuta(processo: ProcessoExtraido) -> list[ResultadoItem]:
    resultados: list[ResultadoItem] = []
    minuta = processo.minuta_contrato

    if minuta is None:
        resultados.append(_inconforme(
            _DOC_MIN,
            "Presença da Minuta",
            "Minuta do Contrato não localizada no processo. "
            f"Obrigatória para DL com Contrato Padrão ({REGRAS_MINUTA_CONTRATO['norma']}). "
            "Deve ser enviada em formato DOCX com os campos em vermelho preenchidos.",
            Providencia.CORRIGIR,
        ))
        return resultados

    resultados.append(_conforme(_DOC_MIN, "Presença da Minuta", "Minuta do Contrato localizada ✓"))

    # Campos obrigatórios mínimos
    campos_ausentes = []
    if not minuta.objeto:
        campos_ausentes.append("Objeto do contrato")
    if minuta.valor_global is None:
        campos_ausentes.append("Valor global (R$)")
    if not minuta.gestor_contrato:
        campos_ausentes.append("Gestor do contrato")
    if not minuta.fiscal_administrativo:
        campos_ausentes.append("Fiscal administrativo")
    if not minuta.contratado_cnpj:
        campos_ausentes.append("CNPJ do contratado")
    if not minuta.prazo_vigencia:
        campos_ausentes.append("Prazo de vigência")

    if campos_ausentes:
        resultados.append(_inconforme(
            _DOC_MIN,
            "Campos em Vermelho – Preenchimento",
            f"Campo(s) obrigatório(s) não identificado(s): {', '.join(campos_ausentes)}. "
            f"Todos os campos em vermelho do modelo devem ser preenchidos: "
            f"{', '.join(REGRAS_MINUTA_CONTRATO['campos_em_vermelho'][:4])} (...).",
            Providencia.CORRIGIR,
        ))
    else:
        resultados.append(_conforme(
            _DOC_MIN,
            "Campos em Vermelho – Preenchimento",
            "Campos obrigatórios da Minuta identificados ✓",
        ))

    if not minuta.campos_vermelhos_preenchidos:
        resultados.append(_inconforme(
            _DOC_MIN,
            "Estrutura da Minuta",
            "Não foi possível confirmar cláusulas numeradas na Minuta. "
            "Verificar se o modelo aprovado foi utilizado sem supressão de cláusulas.",
        ))
    else:
        resultados.append(_conforme(
            _DOC_MIN,
            "Estrutura da Minuta",
            "Cláusulas numeradas identificadas na Minuta ✓",
        ))

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Portaria de Designação
# ─────────────────────────────────────────────────────────────────────────────

def _regras_portaria(processo: ProcessoExtraido) -> list[ResultadoItem]:
    resultados: list[ResultadoItem] = []
    portaria = processo.portaria

    if portaria is None:
        resultados.append(_inconforme(
            _DOC_PORT,
            "Presença da Portaria",
            "Portaria de designação de Gestor e Fiscais não localizada. "
            f"Obrigatória ({REGRAS_PORTARIA_DESIGNACAO['norma']}). "
            "Deve designar Gestor, Fiscal Administrativo e Fiscal Técnico.",
            Providencia.CORRIGIR,
        ))
        return resultados

    resultados.append(_conforme(_DOC_PORT, "Presença da Portaria", "Portaria localizada ✓"))

    if not portaria.numero_portaria:
        resultados.append(_inconforme(
            _DOC_PORT,
            "Número da Portaria",
            "Número da Portaria não identificado. Verificar se o documento é a Portaria vigente.",
        ))
    else:
        resultados.append(_conforme(_DOC_PORT, "Número da Portaria", f"Portaria nº {portaria.numero_portaria} ✓"))

    if not portaria.gestor_designado:
        resultados.append(_inconforme(
            _DOC_PORT,
            "Gestor do Contrato – Designação",
            "Nome do Gestor do Contrato não identificado na Portaria.",
            Providencia.CORRIGIR,
        ))
    else:
        resultados.append(_conforme(
            _DOC_PORT, "Gestor do Contrato – Designação",
            f"Gestor designado: {portaria.gestor_designado} ✓",
        ))

    if not portaria.fiscal_administrativo_designado:
        resultados.append(_inconforme(
            _DOC_PORT,
            "Fiscal Administrativo – Designação",
            "Fiscal Administrativo não identificado na Portaria.",
            Providencia.CORRIGIR,
        ))
    else:
        resultados.append(_conforme(
            _DOC_PORT, "Fiscal Administrativo – Designação",
            f"Fiscal Administrativo: {portaria.fiscal_administrativo_designado} ✓",
        ))

    if not portaria.assinada:
        resultados.append(_inconforme(
            _DOC_PORT,
            "Assinatura da Portaria",
            "Assinatura da autoridade competente (PGJ ou SG) não identificada na Portaria.",
            Providencia.CORRIGIR,
        ))
    else:
        resultados.append(_conforme(_DOC_PORT, "Assinatura da Portaria", "Portaria assinada ✓"))

    # Verificar coerência: gestor designado na portaria × gestor na minuta
    if (
        portaria.gestor_designado
        and processo.minuta_contrato
        and processo.minuta_contrato.gestor_contrato
    ):
        gestor_port = _norm(portaria.gestor_designado)
        gestor_min  = _norm(processo.minuta_contrato.gestor_contrato)
        # Verificação simples de sobreposição de tokens
        tokens_port = set(gestor_port.split())
        tokens_min  = set(gestor_min.split())
        overlap = tokens_port & tokens_min - {"do", "de", "da", "e", "o", "a"}
        if not overlap:
            resultados.append(_inconforme(
                _DOC_PORT,
                "Coerência Portaria × Minuta (Gestor)",
                f"Gestor na Portaria ('{portaria.gestor_designado}') parece divergir "
                f"do Gestor na Minuta ('{processo.minuta_contrato.gestor_contrato}'). "
                "Verificar se são o mesmo servidor.",
            ))
        else:
            resultados.append(_conforme(
                _DOC_PORT,
                "Coerência Portaria × Minuta (Gestor)",
                "Gestor coincide entre Portaria e Minuta ✓",
            ))

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Certidão de Idoneidade
# ─────────────────────────────────────────────────────────────────────────────

def _regras_certidao_idoneidade(processo: ProcessoExtraido) -> list[ResultadoItem]:
    resultados: list[ResultadoItem] = []
    cert = processo.certidao_idoneidade

    if cert is None:
        resultados.append(_inconforme(
            _DOC_IDAD,
            "Presença da Certidão de Idoneidade",
            "Certidão de Idoneidade não localizada. "
            "Obrigatória para DL com Contrato Padrão: verificar TCU, CNJ, CEIS, "
            "ComprasNet-BA e Portal MPBA antes da contratação.",
            Providencia.CORRIGIR,
        ))
        return resultados

    resultados.append(_conforme(_DOC_IDAD, "Presença", "Certidão de Idoneidade localizada ✓"))

    cadastros = REGRAS_CERTIDAO_IDONEIDADE["cadastros_obrigatorios"]
    mapa = {
        "tcu": cert.tcu_regular,
        "cnj": cert.cnj_regular,
        "ceis": cert.ceis_regular,
        "comprasnet_ba": cert.comprasnet_ba_regular,
        "portal_mpba": cert.portal_mpba_regular,
    }

    for cad in cadastros:
        cid = cad["id"]
        status = mapa.get(cid)
        if status is None:
            resultados.append(_inconforme(
                _DOC_IDAD,
                f"Consulta {cad['nome']}",
                f"Resultado da consulta ao {cad['nome']} não identificado no documento. "
                "Verificar se a consulta foi realizada e o resultado registrado.",
            ))
        elif status is False:
            resultados.append(_inconforme(
                _DOC_IDAD,
                f"Restrição – {cad['nome']}",
                f"Fornecedor com restrição no {cad['nome']}. "
                f"{REGRAS_CERTIDAO_IDONEIDADE['acao_se_impedido']}",
                Providencia.CORRIGIR,
            ))
        else:
            resultados.append(_conforme(
                _DOC_IDAD,
                f"Consulta {cad['nome']}",
                f"Sem restrições no {cad['nome']} ✓",
            ))

    if cert.sem_restricoes:
        resultados.append(_conforme(
            _DOC_IDAD,
            "Resultado Geral – Idoneidade",
            "Fornecedor sem restrições em todos os cadastros verificados ✓",
        ))

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Restrições por objeto (MEI, Água Mineral, Mensageiro)
# ─────────────────────────────────────────────────────────────────────────────

_OBJETOS_ESPECIFICOS = NORMAS_CONTRATO_PADRAO["documentos_especificos_por_objeto"]

_KW_AGUA_MINERAL    = ["agua mineral", "agua potavel", "agua envasada"]
_KW_MENSAGEIRO      = ["mensageiro", "motoboy", "motociclista", "entregador"]
_KW_MONITORAMENTO   = ["monitoramento", "vigilancia eletronica", "cftv", "cameras de seguranca", "rastreamento"]


def _regras_objeto_especifico(processo: ProcessoExtraido) -> list[ResultadoItem]:
    resultados: list[ResultadoItem] = []

    # Extrair objeto do DFD ou TR para análise
    objeto = ""
    if processo.dfd and processo.dfd.objeto:
        objeto = processo.dfd.objeto
    elif processo.tr and hasattr(processo.tr, "objeto") and processo.tr.objeto:
        objeto = processo.tr.objeto

    if not objeto:
        return resultados

    obj_n = _norm(objeto)

    # ── Monitoramento: não pode contratar MEI ─────────────────────────────
    if any(kw in obj_n for kw in _KW_MONITORAMENTO):
        restricao = _OBJETOS_ESPECIFICOS["servicos_monitoramento"]
        resultados.append(ResultadoItem(
            documento="Restrição por Objeto",
            item="Restrição MEI – Serviços de Monitoramento",
            status=StatusRegra.PENDENCIA,
            descricao=(
                f"{restricao['motivo']} "
                "Verificar natureza jurídica do fornecedor selecionado: "
                "MEI não pode ser contratado para este tipo de serviço."
            ),
            providencia=Providencia.CORRIGIR,
        ))

    # ── Água Mineral: Alvará de Vigilância Sanitária ──────────────────────
    if any(kw in obj_n for kw in _KW_AGUA_MINERAL):
        docs_obrigatorios = _OBJETOS_ESPECIFICOS["agua_mineral"]
        resultados.append(ResultadoItem(
            documento="Documento Específico por Objeto",
            item="Alvará de Vigilância Sanitária – Água Mineral",
            status=StatusRegra.PENDENCIA,
            descricao=(
                f"Objeto envolve {objeto[:80]}. "
                f"Documentos adicionais obrigatórios: {', '.join(docs_obrigatorios)}. "
                "Verificar presença no processo."
            ),
            providencia=Providencia.CORRIGIR,
        ))

    # ── Mensageiro / Motoboy: CNH + documento do veículo ─────────────────
    if any(kw in obj_n for kw in _KW_MENSAGEIRO):
        docs_obrigatorios = _OBJETOS_ESPECIFICOS["mensageiro_motoboy"]
        resultados.append(ResultadoItem(
            documento="Documento Específico por Objeto",
            item="CNH e Documento do Veículo – Mensageiro/Motoboy",
            status=StatusRegra.PENDENCIA,
            descricao=(
                f"Objeto envolve serviço de mensageiro/motoboy. "
                f"Documentos adicionais obrigatórios: {', '.join(docs_obrigatorios)}. "
                "Verificar presença no processo."
            ),
            providencia=Providencia.CORRIGIR,
        ))

    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9\s]", " ", sem_acento.lower())


def _conforme(documento: str, item: str, descricao: str) -> ResultadoItem:
    return ResultadoItem(
        documento=documento,
        item=item,
        status=StatusRegra.CONFORME,
        descricao=descricao,
        providencia=Providencia.PROSSEGUIR,
    )


def _inconforme(
    documento: str,
    item: str,
    descricao: str,
    providencia: Providencia = Providencia.CORRIGIR,
) -> ResultadoItem:
    return ResultadoItem(
        documento=documento,
        item=item,
        status=StatusRegra.INCONFORME,
        descricao=descricao,
        providencia=providencia,
    )
