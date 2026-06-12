"""Regras normativas do TR – Serviços e Aquisições (schema unificado).

Fundamento: Modelos TR Serviços e TR Aquisições MPBA (Jan/2026)
            + Ato Normativo MPBA nº 048/2024 + Lei 14.133/2021.
"""

from __future__ import annotations
from domain.tr_unificado import TRServicosExtraido, TRAquisicoesExtraido
from domain.processo import ProcessoExtraido
from schemas.responses import ResultadoItem, Providencia
from .base import ok, inconforme, pendencia
from knowledge_base.normas import (
    ESTRUTURA_TR_SERVICOS,
    ESTRUTURA_TR_AQUISICOES,
    REGRAS_PDM_CATMAT,
)

_DOC = "Termo de Referência"


def aplicar_regras_tr(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tr = processo.tr
    if tr is None:
        return [inconforme(_DOC, "Presença", "TR não localizado no processo.", Providencia.CORRIGIR)]

    resultados: list[ResultadoItem] = []

    # ── 1.1 – Objeto ─────────────────────────────────────────────────────────

    if not tr.objeto:
        resultados.append(inconforme(_DOC, "1.1 – Objeto", "Objeto não identificado no TR."))
    else:
        resultados.append(ok(_DOC, "1.1 – Objeto", tr.objeto[:80]))

    # ── Textos exemplificativos não removidos ────────────────────────────────

    if tr.contem_texto_verde:
        resultados.append(inconforme(
            _DOC, "Texto em Verde",
            "Texto exemplificativo em verde deve ser excluído do TR antes da entrega.",
        ))
    if tr.contem_texto_roxo:
        resultados.append(inconforme(
            _DOC, "Texto em Roxo",
            "Texto de orientação em roxo deve ser excluído do TR antes da entrega.",
        ))

    # ── Fundamentação / justificativa ────────────────────────────────────────

    if not tr.fundamentacao:
        resultados.append(pendencia(
            _DOC, "Fundamentação",
            "Justificativa/fundamentação da contratação não identificada automaticamente. "
            "Verificar se a seção está presente e adequadamente preenchida.",
        ))
    else:
        resultados.append(ok(_DOC, "Fundamentação", "Presente."))

    # ── 2.1.1 – Base Legal ───────────────────────────────────────────────────

    bl = tr.base_legal
    if not bl.cita_lei_14133_2021:
        resultados.append(inconforme(_DOC, "2.1.1 – Base Legal", "Lei nº 14.133/2021 não citada."))
    else:
        resultados.append(ok(_DOC, "2.1.1 – Base Legal", "Lei 14.133/2021 citada."))

    # Artigo × tipo de TR
    eh_engenharia = isinstance(tr, TRServicosExtraido) and tr.eh_engenharia
    artigo_esperado = "art. 75, inciso I" if eh_engenharia else "art. 75, inciso II"
    if bl.artigo_inciso and bl.artigo_inciso != artigo_esperado:
        resultados.append(inconforme(
            _DOC, "2.1.1 – Artigo",
            f"Artigo incorreto: '{bl.artigo_inciso}'. Esperado: '{artigo_esperado}'.",
        ))
    elif bl.artigo_inciso:
        resultados.append(ok(_DOC, "2.1.1 – Artigo", bl.artigo_inciso))
    else:
        resultados.append(pendencia(
            _DOC, "2.1.1 – Artigo/Inciso",
            f"Artigo/inciso da Lei 14.133/2021 não identificado. "
            f"Verificar se consta '{artigo_esperado}'.",
        ))

    # ── 2.1.2 – Divulgação no Portal MPBA ───────────────────────────────────

    div = tr.divulgacao
    if not div.opcao:
        resultados.append(inconforme(_DOC, "2.1.2 – Divulgação", "Opção de divulgação não identificada."))
    elif div.opcao == "A":
        if not div.justificativa_a:
            resultados.append(inconforme(
                _DOC, "2.1.2 – Divulgação Opção A",
                "Justificativa obrigatória para não divulgar no Portal MPBA.",
            ))
        else:
            resultados.append(ok(_DOC, "2.1.2 – Divulgação A", "Justificativa presente."))
    elif div.opcao == "B":
        erros = []
        if not div.email:
            erros.append("e-mail institucional (@mpba.mp.br)")
        elif not div.email.lower().endswith("@mpba.mp.br"):
            erros.append(f"e-mail deve ser institucional @mpba.mp.br (encontrado: {div.email})")
        if not div.telefone:
            erros.append("telefone")
        if div.prazo_dias_uteis is None:
            erros.append("prazo em dias úteis")
        elif div.prazo_dias_uteis < 3:
            resultados.append(inconforme(
                _DOC, "2.1.2 – Prazo Divulgação",
                f"Prazo de divulgação ({div.prazo_dias_uteis} du) inferior ao mínimo legal "
                f"de 3 dias úteis (art. 75, §3º, Lei 14.133/2021).",
            ))
        if erros:
            resultados.append(inconforme(
                _DOC, "2.1.2 – Divulgação Opção B",
                f"Campo(s) obrigatório(s) ausente(s): {', '.join(erros)}.",
            ))
        else:
            resultados.append(ok(_DOC, "2.1.2 – Divulgação B", "Dados completos."))

    
    # ── 2.2.1 – Habilitação Jurídica ─────────────────────────────────────────

    hab = tr.habilitacao
    if not hab.juridica_pj and not hab.juridica_pf:
        resultados.append(inconforme(_DOC, "2.2.1 – Hab. Jurídica", "Nenhuma opção assinalada."))
    else:
        resultados.append(ok(_DOC, "2.2.1 – Hab. Jurídica", "Opção identificada."))

    # ── 2.2.2 – Regularidade Fiscal, Social e Trabalhista ────────────────────

    fst_faltando = []
    for campo, rotulo in [
        ("fiscal_certidao_federal", "Certidão Federal + Dívida Ativa"),
        ("fiscal_certidao_estadual", "Certidão Estadual"),
        ("fiscal_certidao_municipal", "Certidão Municipal"),
        ("fiscal_cndt", "CNDT"),
        ("fiscal_fgts", "FGTS/CRF"),
    ]:
        if not getattr(hab, campo, False):
            fst_faltando.append(rotulo)
    if fst_faltando:
        resultados.append(inconforme(
            _DOC, "2.2.2 – Fiscal/Social/Trabalhista",
            f"Opções obrigatórias não identificadas: {', '.join(fst_faltando)}.",
        ))
    else:
        resultados.append(ok(_DOC, "2.2.2 – Fiscal/Social/Trabalhista", "Todas as certidões previstas."))

    # ── 2.2.3 – Habilitação Técnica ──────────────────────────────────────────

    if hab.tecnica_opcao == "B" and not hab.tecnica_requisitos:
        resultados.append(inconforme(
            _DOC, "2.2.3 – Hab. Técnica",
            "Requisitos técnicos obrigatórios quando Opção B selecionada.",
        ))

    # ── 2.2.4 – Qualificação Econômico-Financeira ────────────────────────────

    if hab.econom_opcao == "C" and not hab.econom_justificativa:
        resultados.append(inconforme(
            _DOC, "2.2.4 – Econômica Opção C",
            "Justificativa obrigatória para exigência de Balanço Patrimonial (Opção C).",
        ))
    if hab.econom_opcao == "D":
        if hab.econom_percentual_d is not None and hab.econom_percentual_d > 10:
            resultados.append(inconforme(
                _DOC, "2.2.4 – Capital Social",
                f"Percentual de capital social ({hab.econom_percentual_d}%) excede limite legal de 10% "
                f"(art. 69, II, Lei 14.133/2021).",
            ))
        if not hab.econom_justificativa:
            resultados.append(inconforme(
                _DOC, "2.2.4 – Econômica Opção D",
                "Justificativa obrigatória para exigência de Capital Social Mínimo (Opção D).",
            ))

    # ── Apenso I – planilha de itens ─────────────────────────────────────────

    if not tr.apenso_i_presente:
        resultados.append(pendencia(
            _DOC, "Apenso I – Planilha de Itens",
            "Apenso I (planilha de itens/serviços com quantidade e valores estimados) não "
            "localizado automaticamente. Verificar se está presente no processo.",
        ))
    else:
        resultados.append(ok(_DOC, "Apenso I", "Planilha de itens presente."))

    # ── 1.6/1.7 – Formalização ───────────────────────────────────────────────

    if not tr.formalizacao_opcao:
        resultados.append(pendencia(
            _DOC, "1.6/1.7 – Formalização",
            "Opção de formalização não identificada automaticamente. "
            "Verificar se Opção A (NE/instrumento substitutivo) está assinalada, "
            "conforme exigido para Dispensa de Licitação sem contrato.",
        ))
    elif tr.formalizacao_opcao.upper() != "A":
        resultados.append(inconforme(
            _DOC, "1.6/1.7 – Formalização",
            f"Formalização Opção {tr.formalizacao_opcao.upper()} é incompatível com "
            "Dispensa de Licitação sem contrato. Obrigatório selecionar Opção A "
            "(Nota de Empenho ou instrumento substitutivo).",
        ))
    else:
        resultados.append(ok(_DOC, "1.6/1.7 – Formalização", "Opção A – NE/instrumento substitutivo."))

    # ── Responsável pelo TR ───────────────────────────────────────────────────

    if not tr.responsavel_nome:
        resultados.append(pendencia(
            _DOC, "Responsável / Assinatura",
            "Nome do responsável pela elaboração do TR não identificado automaticamente. "
            "Verificar se consta nome, cargo e assinatura ao final do documento.",
        ))
    else:
        resultados.append(ok(_DOC, "Responsável", tr.responsavel_nome[:60]))

    # ── Regras específicas por tipo ──────────────────────────────────────────

    if isinstance(tr, TRServicosExtraido):
        resultados.extend(_regras_servicos(tr))
    elif isinstance(tr, TRAquisicoesExtraido):
        resultados.extend(_regras_aquisicoes(tr))

    return resultados


def _regras_servicos(tr: TRServicosExtraido) -> list[ResultadoItem]:
    """Regras específicas do TR Serviços (modelo MPBA Jan/2026)."""
    r: list[ResultadoItem] = []

    # ── 1.3 – Natureza do Objeto ─────────────────────────────────────────────
    # A = serviço não continuado (execução imediata)
    # B = serviço parcelado (execuções parciais sucessivas)
    # C = serviço continuado (exige sub-opção C1–C4 e justificativa)

    if not tr.natureza_objeto:
        r.append(inconforme(
            _DOC, "1.3 – Natureza do Objeto",
            "Natureza do objeto não identificada (A: não continuado, B: parcelado, C: continuado).",
        ))
    elif tr.natureza_objeto.upper() == "C":
        if not tr.natureza_objeto_c_subopcao:
            r.append(inconforme(
                _DOC, "1.3 – Natureza do Objeto – Sub-opção",
                "Serviço Continuado (Opção C): sub-opção obrigatória (C1, C2, C3 ou C4).",
            ))
        else:
            r.append(ok(_DOC, "1.3 – Natureza do Objeto – Sub-opção", tr.natureza_objeto_c_subopcao))
        if not tr.natureza_objeto_c_justificativa:
            r.append(inconforme(
                _DOC, "1.3 – Natureza do Objeto – Justificativa",
                "Serviço Continuado (Opção C): justificativa obrigatória.",
            ))
        else:
            r.append(ok(_DOC, "1.3 – Natureza do Objeto", "Opção C – justificativa presente."))
    else:
        r.append(ok(_DOC, "1.3 – Natureza do Objeto", f"Opção {tr.natureza_objeto}"))

    # ── 3.1 – Regime de Execução ─────────────────────────────────────────────

    if not tr.regime_execucao:
        r.append(inconforme(_DOC, "3.1 – Regime de Execução", "Opção não identificada."))
    else:
        r.append(ok(_DOC, "3.1 – Regime de Execução", tr.regime_execucao[:60]))

    # ── 3.3.1 – Local de Execução + CEP ──────────────────────────────────────

    if not tr.local_execucao:
        r.append(inconforme(_DOC, "3.3.1 – Local de Execução", "Endereço não identificado."))
    elif not tr.cep_execucao:
        r.append(inconforme(_DOC, "3.3.1 – CEP", "CEP obrigatório no local de execução."))
    else:
        r.append(ok(_DOC, "3.3.1 – Local de Execução", f"{tr.local_execucao[:60]} – CEP {tr.cep_execucao}"))

    # ── 3.4 – Prazo de execução dos serviços ─────────────────────────────────

    if not tr.prazo_execucao_dias:
        r.append(pendencia(
            _DOC, "3.4 – Prazo de Execução",
            "Prazo de execução dos serviços não identificado automaticamente. "
            "Verificar se está preenchido e é compatível com o objeto.",
        ))
    else:
        r.append(ok(_DOC, "3.4 – Prazo de Execução", f"{tr.prazo_execucao_dias} dias."))

    # ── 3.5 – Garantia do Serviço ────────────────────────────────────────────
    # A = sem garantia  B = garantia legal  C = garantia contratada
    # D = híbrido (legal + contratada)  E = Apenso II
    # Opções C e D exigem justificativa.

    if not tr.garantia_opcao:
        r.append(pendencia(
            _DOC, "3.5 – Garantia do Serviço",
            "Opção de garantia do serviço não identificada automaticamente. "
            "Verificar se opção A (CDC não aplicável), B (garantia legal CDC), "
            "C (garantia contratada), D (híbrido) ou E (Apenso II) está assinalada.",
        ))
    elif tr.garantia_opcao.upper() in ("C", "D") and not tr.garantia_justificativa:
        r.append(inconforme(
            _DOC, "3.5 – Garantia do Serviço",
            f"Opção {tr.garantia_opcao.upper()} exige justificativa obrigatória para a garantia contratada.",
        ))
    else:
        r.append(ok(_DOC, "3.5 – Garantia do Serviço", f"Opção {tr.garantia_opcao}"))

    # ── 3.6 – Subcontratação ─────────────────────────────────────────────────

    if not tr.subcontratacao_opcao:
        r.append(pendencia(
            _DOC, "3.6 – Subcontratação",
            "Opção de subcontratação não identificada automaticamente. "
            "Verificar se opção A (vedada) ou B (admitida parcialmente) está assinalada.",
        ))
    else:
        r.append(ok(_DOC, "3.6 – Subcontratação", f"Opção {tr.subcontratacao_opcao}"))

    # ── 3.13 – Vigência da Contratação ───────────────────────────────────────

    if not tr.vigencia_opcao:
        r.append(pendencia(
            _DOC, "3.13 – Vigência da Contratação",
            "Vigência da contratação não identificada automaticamente. "
            "Verificar se prazo e forma de contagem estão corretamente preenchidos (seção 3.13).",
        ))
    else:
        r.append(ok(_DOC, "3.13 – Vigência da Contratação", f"Opção {tr.vigencia_opcao}"))

    # ── 3.16 – Garantia Contratual (performance bond) ────────────────────────
    # Seção 3.16 conforme modelo TR Serviços MPBA Jan/2026
    # A = não será exigida | B = será exigida (percentual ≤ 5%)

    if not tr.garantia_contratual_opcao:
        r.append(pendencia(
            _DOC, "3.16 – Garantia Contratual",
            "Opção de garantia contratual não identificada automaticamente. "
            "Verificar se opção A (não exigida) ou B (exigida, com percentual ≤ 5%) está assinalada.",
        ))
    else:
        r.append(ok(_DOC, "3.16 – Garantia Contratual", f"Opção {tr.garantia_contratual_opcao}"))

    # ── 3.7.4 – Multas – verificação humana obrigatória ──────────────────────

    r.append(pendencia(
        _DOC, "3.7.4 – Multas",
        "Verificar se os percentuais de multa estão preenchidos corretamente: "
        "mora (0,5%/dia) e inexecução total (até 30% do valor do contrato), "
        "conforme padrão normativo MPBA.",
    ))

    return r


def _regras_aquisicoes(tr: TRAquisicoesExtraido) -> list[ResultadoItem]:
    """Regras específicas do TR Aquisições (modelo MPBA Jan/2026)."""
    r: list[ResultadoItem] = []

    # ── 1.1 – Declaração não é bem de luxo ──────────────────────────────────
    # Ato Normativo MPBA nº 004/2024 – obrigatório somente no TR Aquisições

    if not tr.declara_nao_bem_de_luxo:
        r.append(inconforme(
            _DOC, "1.1 – Bem de Luxo",
            "Declaração obrigatória ausente: Ato Normativo MPBA nº 004/2024 "
            "(o TR deve declarar que o objeto não se enquadra como bem de luxo).",
        ))
    else:
        r.append(ok(_DOC, "1.1 – Bem de Luxo", "Declaração presente."))

    # ── 1.2 – Marca/Modelo ───────────────────────────────────────────────────

    if not tr.marca_modelo_opcao:
        r.append(inconforme(
            _DOC, "1.2 – Marca/Modelo",
            "Opção de marca/modelo não identificada. Obrigatório assinalar opção A, B ou C.",
        ))
    elif tr.marca_modelo_opcao.upper() in ("B", "C"):
        if not tr.marca_modelo_justificativa:
            r.append(inconforme(
                _DOC, "1.2 – Marca/Modelo",
                f"Justificativa obrigatória para Opção {tr.marca_modelo_opcao} "
                f"(art. 41, §1º, Lei 14.133/2021).",
            ))
        else:
            r.append(ok(_DOC, "1.2 – Marca/Modelo", f"Opção {tr.marca_modelo_opcao} – justificativa presente."))
    else:
        r.append(ok(_DOC, "1.2 – Marca/Modelo", f"Opção {tr.marca_modelo_opcao}"))

    # ── 1.3 – Justificativa da quantidade ────────────────────────────────────

    if not tr.justificativa_quantidade:
        r.append(inconforme(
            _DOC, "1.3 – Justificativa da Quantidade",
            "Campo obrigatório ausente (modelo TR Aquisições MPBA Jan/2026, item 1.3).",
        ))
    else:
        r.append(ok(_DOC, "1.3 – Justificativa da Quantidade", "Presente."))

    # ── 1.4 – Natureza do Objeto ─────────────────────────────────────────────

    if not tr.natureza_objeto:
        r.append(inconforme(
            _DOC, "1.4 – Natureza do Objeto",
            "Natureza do objeto não identificada (A: fornecimento imediato, "
            "B: parcelado, C: continuado).",
        ))
    elif tr.natureza_objeto.upper() == "C" and not tr.natureza_objeto_c_justificativa:
        r.append(inconforme(
            _DOC, "1.4 – Natureza do Objeto",
            "Opção C (fornecimento continuado) exige justificativa obrigatória.",
        ))
    else:
        r.append(ok(_DOC, "1.4 – Natureza do Objeto", f"Opção {tr.natureza_objeto}"))

    # ── 3.2.1 – Prazo de Entrega ─────────────────────────────────────────────
    # (prazo NE já verificado nas regras comuns; registra PENDENCIA se prazo em horas)

    if tr.prazo_entrega_horas:
        r.append(pendencia(
            _DOC, "3.2.1 – Prazo de Entrega (horas)",
            f"Prazo de entrega em horas ({tr.prazo_entrega_horas}h) identificado. "
            "Verificar se é compatível com o objeto e se está corretamente preenchido.",
        ))

    # ── 3.2.4 – Local de Entrega + CEP ───────────────────────────────────────

    if not tr.local_entrega:
        r.append(inconforme(_DOC, "3.2.4 – Local de Entrega", "Endereço não identificado."))
    elif not tr.cep_entrega:
        r.append(inconforme(_DOC, "3.2.4 – CEP de Entrega", "CEP obrigatório no local de entrega."))
    else:
        r.append(ok(_DOC, "3.2.4 – Local de Entrega", f"{tr.local_entrega[:60]} – CEP {tr.cep_entrega}"))

    # ── 3.3 – Montagem ───────────────────────────────────────────────────────

    if not tr.montagem_opcao:
        r.append(pendencia(
            _DOC, "3.3 – Montagem",
            "Opção de montagem não identificada automaticamente. "
            "Verificar se opção A (entregues montados), B (desmontados) ou "
            "C (desmontados com montagem) está assinalada.",
        ))
    else:
        r.append(ok(_DOC, "3.3 – Montagem", f"Opção {tr.montagem_opcao}"))

    # ── 3.4 – Instalação ─────────────────────────────────────────────────────

    if not tr.instalacao_opcao:
        r.append(pendencia(
            _DOC, "3.4 – Instalação",
            "Opção de instalação não identificada automaticamente. "
            "Verificar se opção A (sem instalação) ou B (com instalação) está assinalada.",
        ))
    else:
        r.append(ok(_DOC, "3.4 – Instalação", f"Opção {tr.instalacao_opcao}"))

    # ── 3.6.1 – Garantia do Produto ──────────────────────────────────────────

    if not tr.garantia_opcao:
        r.append(pendencia(
            _DOC, "3.6.1 – Garantia do Produto",
            "Opção de garantia do produto não identificada automaticamente. "
            "Verificar se opção A (CDC não aplicável), B (garantia legal CDC), "
            "C (garantia contratada), D (híbrido) ou E (Apenso II) está assinalada.",
        ))
    elif tr.garantia_opcao.upper() in ("C", "D") and not tr.garantia_justificativa:
        r.append(inconforme(
            _DOC, "3.6.1 – Garantia do Produto",
            f"Opção {tr.garantia_opcao.upper()} exige justificativa obrigatória para a garantia contratada.",
        ))
    else:
        r.append(ok(_DOC, "3.6.1 – Garantia do Produto", f"Opção {tr.garantia_opcao}"))

    # ── 3.7 – Subcontratação ─────────────────────────────────────────────────

    if not tr.subcontratacao_opcao:
        r.append(pendencia(
            _DOC, "3.7 – Subcontratação",
            "Opção de subcontratação não identificada automaticamente. "
            "Verificar se opção A (vedada) ou B (admitida parcialmente) está assinalada.",
        ))
    else:
        r.append(ok(_DOC, "3.7 – Subcontratação", f"Opção {tr.subcontratacao_opcao}"))

    # ── 3.14 – Vigência da Contratação ───────────────────────────────────────

    if not tr.vigencia_opcao:
        r.append(pendencia(
            _DOC, "3.14 – Vigência da Contratação",
            "Vigência da contratação não identificada automaticamente. "
            "Verificar se prazo e forma de contagem estão corretamente preenchidos (seção 3.14).",
        ))
    else:
        r.append(ok(_DOC, "3.14 – Vigência da Contratação", f"Opção {tr.vigencia_opcao}"))

    # ── 3.9.4 – Multas – verificação humana obrigatória ──────────────────────

    r.append(pendencia(
        _DOC, "3.9.4 – Multas",
        "Verificar se os percentuais de multa estão preenchidos corretamente: "
        "mora (0,5%/dia) e inexecução total (até 30% do valor da contratação), "
        "conforme padrão normativo MPBA.",
    ))

    return r
