"""Regras normativas do DFD.

Fundamento: Modelo DFD MPBA + Ato Normativo MPBA nº 048/2024 + Lei 14.133/2021.
Referência: knowledge_base.normas.ESTRUTURA_DFD
"""

from __future__ import annotations
import re
from domain.dfd import DFDExtraido
from domain.processo import ProcessoExtraido
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme, pendencia
from knowledge_base.normas import ESTRUTURA_DFD

_DOC = "DFD"


def aplicar_regras_dfd(processo: ProcessoExtraido) -> list[ResultadoItem]:
    dfd = processo.dfd
    if dfd is None:
        return [inconforme(_DOC, "Presença", "DFD não localizado no processo.", Providencia.CORRIGIR)]

    resultados: list[ResultadoItem] = []

    # Objeto
    if not dfd.objeto:
        resultados.append(inconforme(_DOC, "Item 1 – Objeto", "Objeto não identificado no DFD."))
    else:
        resultados.append(ok(_DOC, "Item 1 – Objeto", f"Objeto: {dfd.objeto[:80]}"))
        # Coerência DFD × TR será verificada pela IA

    # TIC
    if not dfd.tic:
        resultados.append(inconforme(_DOC, "Item 2 – TIC", "Campo TIC não assinalado."))
    else:
        resultados.append(ok(_DOC, "Item 2 – TIC", f"TIC: {dfd.tic}"))

    # Unidade solicitante
    if not dfd.unidade_solicitante:
        resultados.append(inconforme(_DOC, "Item 3 – Unidade Solicitante", "Campo obrigatório não identificado."))
    else:
        resultados.append(ok(_DOC, "Item 3 – Unidade Solicitante", dfd.unidade_solicitante))

    # Unidade gestora
    if not dfd.unidade_gestora:
        resultados.append(inconforme(_DOC, "Item 4 – Unidade Gestora", "Campo não identificado."))
    else:
        padrao = re.match(r"^\d{2}\.\d{3}\s*[–\-]", dfd.unidade_gestora.strip())
        if not padrao:
            resultados.append(inconforme(
                _DOC, "Item 4 – Unidade Gestora",
                f"Formato inválido: '{dfd.unidade_gestora}'. Esperado: 40.10X – Nome / Unidade.",
            ))
        else:
            resultados.append(ok(_DOC, "Item 4 – Unidade Gestora", dfd.unidade_gestora))

    # Origem convênio
    if dfd.origem_convenio == "SIM":
        if not dfd.nome_concedente or not dfd.numero_convenio:
            resultados.append(inconforme(
                _DOC, "Item 5 – Convênio",
                "Convênio assinalado mas nome do concedente ou número do convênio ausente.",
            ))

    # PCA
    if dfd.pca == "NÃO":
        if not dfd.pca_justificativa:
            resultados.append(inconforme(
                _DOC, "PCA – Justificativa",
                "Contratação não prevista no PCA sem justificativa.",
                Providencia.CORRIGIR,
            ))
        elif not dfd.despacho_sga_presente:
            resultados.append(pendencia(
                _DOC, "PCA – Retorno SGA",
                "Justificativa apresentada. Aguardando Despacho/Decisão da SGA.",
                Providencia.SGA,
            ))
        else:
            resultados.append(ok(_DOC, "PCA", "Justificativa + Despacho SGA presentes."))
    elif dfd.pca == "SIM":
        resultados.append(ok(_DOC, "PCA", "Contratação prevista no PCA."))

    # Responsável
    if not dfd.responsavel_nome:
        resultados.append(inconforme(_DOC, "Responsável", "Nome do responsável não identificado."))
    else:
        resultados.append(ok(_DOC, "Responsável", dfd.responsavel_nome))

    # Superior imediato – ciência obrigatória (assinatura ou despacho)
    if not dfd.superior_assinou and not dfd.superior_ciencia:
        resultados.append(inconforme(
            _DOC, "Superior – Ciência",
            "Ciência do superior imediato não localizada (assinatura ou despacho). "
            "Obrigatória conforme modelo DFD MPBA.",
        ))
    else:
        resultados.append(ok(_DOC, "Superior – Ciência", "Ciência do superior registrada."))

    return resultados
