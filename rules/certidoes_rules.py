"""Regras normativas das certidões e documentos da empresa.

Fundamento: Modelos TR Serviços/Aquisições MPBA (Jan/2026), seção 2.2.2
            + Declaração de Não Emprego de Menor (art. 7º XXXIII CF)
            + Declaração CNMP nº 37/2009
            + art. 87, Lei 14.133/2021 (SICAF)
            + Ato Normativo MPBA nº 048/2024.
Referências: knowledge_base.normas.CERTIDOES_OBRIGATORIAS
             knowledge_base.normas.ESTRUTURA_DECLARACAO_MENOR
             knowledge_base.normas.ESTRUTURA_DECLARACAO_CNMP
             knowledge_base.normas.REGRAS_GESTOR_FISCAL
"""

from __future__ import annotations
from datetime import date
from domain.processo import ProcessoExtraido
from domain.base import StatusCertidao
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme
from knowledge_base.normas import (
    CERTIDOES_OBRIGATORIAS,
    ESTRUTURA_DECLARACAO_MENOR,
    ESTRUTURA_DECLARACAO_CNMP,
    REGRAS_GESTOR_FISCAL,
    REGRAS_DOCUMENTO_BANCARIO,
)


def aplicar_regras_certidoes(processo: ProcessoExtraido) -> list[ResultadoItem]:
    r: list[ResultadoItem] = []
    certidoes = processo.certidoes

    if certidoes is None:
        return [inconforme("Certidões", "Presença", "Nenhuma certidão localizada.", Providencia.CORRIGIR)]

    hoje = date.today()
    mapa = [
        ("federal_divida_ativa", "Certidão Federal + Dívida Ativa"),
        ("estadual",             "Certidão Estadual"),
        ("municipal",            "Certidão Municipal"),
        ("cndt",                 "CNDT"),
        ("fgts_crf",             "FGTS – CRF"),
    ]
    for attr, nome in mapa:
        cert = getattr(certidoes, attr)
        if cert.status == StatusCertidao.AUSENTE:
            r.append(inconforme("Certidões", nome, f"{nome}: ausente no processo."))
        elif cert.status == StatusCertidao.POSITIVA:
            r.append(inconforme(
                "Certidões", nome,
                f"{nome}: certidão POSITIVA – empresa impedida de contratar.",
                Providencia.CORRIGIR,
            ))
        else:
            if cert.data_validade and cert.data_validade < hoje:
                r.append(inconforme(
                    "Certidões", nome,
                    f"{nome}: vencida em {cert.data_validade}. Exigir certidão atualizada.",
                ))
            else:
                r.append(ok("Certidões", nome, f"{cert.status.value} ✓"))

    return r


def aplicar_regras_empresa(processo: ProcessoExtraido) -> list[ResultadoItem]:
    r: list[ResultadoItem] = []
    emp = processo.empresa

    if emp is None:
        return [inconforme("Empresa", "Presença", "Documentos da empresa não localizados.", Providencia.CORRIGIR)]

    if not emp.cnpj_valido:
        r.append(inconforme("Empresa", "CNPJ", f"CNPJ inválido ou ausente: {emp.cnpj}."))
    else:
        r.append(ok("Empresa", "CNPJ", f"{emp.cnpj} ✓"))

    # SICAF obrigatório (art. 87, Lei 14.133/2021 + Ato Normativo MPBA 048/2024)
    sicaf_info = REGRAS_GESTOR_FISCAL["sicaf"]
    if not emp.sicaf_presente:
        r.append(inconforme(
            "Empresa", "SICAF",
            f"SICAF ausente. {sicaf_info['descricao']} "
            f"({sicaf_info['norma']}). {sicaf_info['excecao']}",
        ))
    else:
        r.append(ok("Empresa", "SICAF", "Presente ✓"))

    # Comprovante bancário – não pode conter extrato/saldo
    # (Modelo de Proposta MPBA + REGRAS_DOCUMENTO_BANCARIO)
    if emp.comprovante_contem_extrato:
        campos_proibidos = ", ".join(REGRAS_DOCUMENTO_BANCARIO["campos_proibidos"][:3])
        r.append(inconforme(
            "Empresa", "Comprovante Bancário",
            f"Dado financeiro proibido visível ({campos_proibidos}...). "
            "Exigir documento com apenas banco/agência/conta.",
        ))

    # Declaração de Não Emprego de Menor
    # (art. 7º, inciso XXXIII, CF/1988 – modelo MPBA)
    if not emp.declaracao_nao_emprega_menor:
        r.append(inconforme(
            "Empresa", "Declaração – Não Emprega Menor",
            f"Ausente. Obrigatória conforme {ESTRUTURA_DECLARACAO_MENOR['base_legal']}.",
        ))
    else:
        r.append(ok("Empresa", "Declaração – Não Emprega Menor", "Presente ✓"))

    # Declaração CNMP nº 37/2009
    if not emp.declaracao_cnmp_presente:
        r.append(inconforme(
            "Empresa", "Declaração CNMP nº 37/2009",
            f"Ausente. Exigir declaração fundamentada na {ESTRUTURA_DECLARACAO_CNMP['base_legal']}.",
        ))
    elif not emp.menciona_cnmp_37_2009:
        r.append(inconforme(
            "Empresa", "Declaração CNMP – Referência Normativa",
            "Declaração presente, mas não menciona 'Resolução CNMP nº 37/2009'. "
            "Exigir substituição pelo modelo correto.",
        ))
    else:
        r.append(ok("Empresa", "Declaração CNMP nº 37/2009", "Presente e com referência correta ✓"))

    # CNJ 07/2005 é proibido (declarado inconstitucional)
    if emp.menciona_cnj_07_2005:
        termo = ESTRUTURA_DECLARACAO_CNMP["termo_proibido"]
        r.append(inconforme(
            "Empresa", "Declaração - CNJ 07/2005 Proibido",
            f"Referência a '{termo['texto']}' é vedada. {termo['motivo']}",
            Providencia.CORRIGIR,
        ))

    return r
