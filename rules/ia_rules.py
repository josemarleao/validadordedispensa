"""Regras assistidas por IA – análise de conteúdo complementar às regras determinísticas.
# Inclui double-check: IA confirma ou descarta cada INCONFORME/PENDÊNCIA gerada pelas regras.

Estratégia:
  - Uma chamada por documento analisa TODOS os aspectos que a regex não consegue avaliar:
    (a) campos estruturais (checkboxes, opções) não extraídos pelo OCR
    (b) aspectos qualitativos (adequação, substância, coerência)
  - Os itens retornados pela IA com nome EXATO igual a um item determinístico substituem
    esse item na lista final (PENDÊNCIA → CONFORME/INCONFORME via IA).

Documentos cobertos:
  - DFD
  - TR Serviços
  - TR Aquisições
  - Tabela de Preços Orçados
  - Orçamentos / Propostas
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import date
from typing import TypeVar
from domain.processo import ProcessoExtraido
from domain.tr_unificado import TRServicosExtraido, TRAquisicoesExtraido
from schemas.responses import ResultadoItem, StatusRegra, Providencia
from .base import ok, inconforme, pendencia, normalizar_rotulo_regra
from ai.analyzer import analisar

log = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Utilitário: fatiamento inteligente de contexto
# ─────────────────────────────────────────────────────────────────────────────

def _fatiar_secoes(
    texto: str,
    secoes: list[str],
    cabecalho: int = 3000,
    rodape: int = 1500,
    bloco: int = 700,
) -> str:
    """Retorna cabeçalho + rodapé + trechos das seções pedidas.

    Produz ~12 k chars independente do tamanho do TR, garantindo que cada
    chamada à IA só receba o que é relevante para a pergunta.

    Args:
        texto:     texto completo do segmento TR.
        secoes:    lista de números de seção a localizar (ex: ["3.5", "3.6"]).
        cabecalho: chars iniciais sempre incluídos (objeto, fundamentação…).
        rodape:    chars finais sempre incluídos (assinatura, responsável…).
        bloco:     chars extraídos ao redor de cada seção encontrada.
    """
    n = len(texto)
    if n <= cabecalho + rodape:
        return texto

    partes: list[str] = [texto[:cabecalho]]
    miolo = texto[cabecalho: n - rodape]

    for sec in secoes:
        # Tolera ruído de OCR entre dígitos: "3.5" → r"3[^\d\n]{0,3}5"
        parts = sec.split(".")
        if len(parts) == 2:
            pat = rf"(?<!\d){re.escape(parts[0])}[^\d\n]{{0,3}}{re.escape(parts[1])}(?!\d)"
        else:
            pat = re.escape(sec)

        m = re.search(pat, miolo, re.IGNORECASE)
        if m:
            ini = max(0, m.start() - 50)
            fim = min(len(miolo), ini + bloco)
            partes.append(f"\n[...]\n{miolo[ini:fim]}")

    partes.append(f"\n[...]\n{texto[-rodape:]}")
    return "".join(partes)

_DOC_DFD    = "DFD"
_DOC_TR     = "Termo de Referência"
_DOC_PRECOS = "Tabela de Preços Orçados"
_DOC_ORC    = "Orçamentos / Propostas"

_MORA_MAX  = 0.5
_INEX_MAX  = 30.0
_DOUBLE_CHECK_MAX_ITENS_POR_LOTE = 4
_DOUBLE_CHECK_MAX_CARACTERES_BLOCO = 5500
_DOUBLE_CHECK_CLASSIFICACOES_PRESENTE = {
    "PRESENTE_EQUIVALENTE",
    "PRESENTE_VARIACAO_FORMA",
}
T = TypeVar("T")

_DOUBLE_CHECK_TERMOS: dict[str, dict[str, list[str]]] = {
    _DOC_TR: {
        "1.1 – Objeto": ["objeto", "descrição do objeto", "objeto da contratação", "especificação do objeto"],
        "Fundamentação": ["fundamentação", "justificativa", "motivação da contratação", "razão da contratação"],
        "2.1.1 – Base Legal": ["base legal", "lei 14.133", "lei nº 14.133", "art. 75"],
        "2.1.1 – Artigo": ["art. 75", "inciso i", "inciso ii", "base legal"],
        "2.1.1 – Artigo/Inciso": ["art. 75", "inciso i", "inciso ii", "fundamento legal"],
        "2.1.2 – Divulgação": ["portal mpba", "divulgação", "aviso prévio", "publicação", "e-mail", "telefone", "@mpba.mp.br"],
        "2.1.2 – Divulgação Opção B": ["portal mpba", "publicar", "divulgação", "opção b", "e-mail", "@mpba.mp.br", "telefone", "prazo"],
        "2.2.1 – Hab. Jurídica": ["habilitação jurídica", "documentação jurídica"],
        "2.2.2 – Fiscal/Social/Trabalhista": ["regularidade fiscal", "certidão federal", "certidão estadual", "cndt", "fgts"],
        "Apenso I – Planilha de Itens": ["apenso i", "planilha de itens", "planilha de serviços", "quantidade", "valor estimado"],
        "1.6/1.7 – Formalização": ["formalização", "nota de empenho", "instrumento substitutivo", "contrato", "ata de registro"],
        "Responsável / Assinatura": ["responsável", "elaboração", "assinatura", "cargo"],
        "1.3 – Natureza do Objeto": ["natureza do objeto", "serviço continuado", "serviço parcelado", "execução imediata"],
        "1.4 – Natureza do Objeto": ["natureza do objeto", "fornecimento imediato", "fornecimento parcelado", "fornecimento continuado"],
        "3.1 – Regime de Execução": ["regime de execução", "preço global", "preço unitário"],
        "3.4 – Prazo de Execução": ["prazo de execução", "prazo para execução", "cronograma"],
        "3.5 – Garantia do Serviço": ["garantia do serviço", "garantia legal", "garantia contratada"],
        "3.6 – Subcontratação": ["subcontratação", "vedada", "admitida"],
        "3.7 – Subcontratação": ["subcontratação", "vedada", "admitida"],
        "3.6.1 – Garantia do Produto": ["garantia do produto", "garantia legal", "cdc", "apenso ii"],
        "3.13 – Vigência da Contratação": ["vigência da contratação", "vigência", "prazo de vigência"],
        "3.14 – Vigência da Contratação": ["vigência da contratação", "vigência", "prazo de vigência"],
        "3.16 – Garantia Contratual": ["garantia contratual", "seguro garantia", "caução", "performance bond"],
        "3.7.4 – Multas": ["multa", "mora", "inexecução total", "penalidade"],
        "3.9.4 – Multas": ["multa", "mora", "inexecução total", "penalidade"],
    },
    _DOC_DFD: {
        "Objeto": ["objeto", "objeto da futura contratação", "descrição da demanda"],
        "Justificativa PCA": ["pca", "plano de contratações anual", "justificativa"],
        "Coerência Geral": ["unidade solicitante", "unidade gestora", "responsável", "superior imediato"],
    },
    _DOC_PRECOS: {
        "Motivação dos Fornecedores": ["motivação", "justificativa", "fornecedores consultados"],
    },
}


def _ia(item: ResultadoItem) -> ResultadoItem:
    return item.model_copy(update={"via_ia": True})


def _de_avaliacao(documento: str, av: dict) -> ResultadoItem:
    """Converte um item da resposta JSON da IA em ResultadoItem."""
    nome = av.get("item", "Análise IA")
    obs  = av.get("observacao", "")
    if av.get("conforme"):
        return _ia(ok(documento, nome, obs or "Conforme."))
    return _ia(inconforme(documento, nome, obs or "Não conforme."))


def _limpar_bloco(texto: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _extrair_trechos_relevantes(
    texto: str,
    termos: list[str],
    *,
    janela: int = 500,
    max_trechos: int = 6,
) -> str:
    """Monta um contexto compacto com trechos próximos aos termos relevantes.

    Isso ajuda a IA a reconhecer informação equivalente em modelos antigos,
    mesmo quando a nomenclatura ou a ordem das seções diverge do template atual.
    """
    if not texto:
        return ""

    trechos: list[str] = []
    vistos: set[tuple[int, int]] = set()
    for termo in termos:
        for match in re.finditer(re.escape(termo), texto, re.IGNORECASE):
            ini = max(0, match.start() - janela)
            fim = min(len(texto), match.end() + janela)
            chave = (ini // 100, fim // 100)
            if chave in vistos:
                continue
            vistos.add(chave)
            trechos.append(f"[trecho relacionado a '{termo}']\n{_limpar_bloco(texto[ini:fim])}")
            if len(trechos) >= max_trechos:
                return "\n\n".join(trechos)
    return "\n\n".join(trechos)


def _montar_contexto_double_check(
    texto: str,
    doc: str,
    itens: list[ResultadoItem],
) -> str:
    if not texto:
        return ""

    termos_doc = _DOUBLE_CHECK_TERMOS.get(doc, {})
    termos: list[str] = []
    for item in itens:
        termos.extend(termos_doc.get(item.item, []))
        termos.append(item.item)

    partes: list[str] = []
    if len(texto) <= 9000:
        partes.append(texto)
    else:
        partes.append(texto[:3000])
        trechos = _extrair_trechos_relevantes(texto, termos)
        if trechos:
            partes.append(trechos)
        partes.append(texto[-1800:])

    return _limpar_bloco("\n\n[...]\n\n".join(p for p in partes if p))


def _iterar_lotes(itens: list[T], tamanho: int) -> list[list[T]]:
    return [itens[i:i + tamanho] for i in range(0, len(itens), tamanho)]


def _agrupar_blocos_texto(
    blocos: list[str],
    *,
    max_caracteres: int = _DOUBLE_CHECK_MAX_CARACTERES_BLOCO,
    max_paginas_por_grupo: int = 4,
) -> list[str]:
    """Agrupa páginas em blocos controlados para reduzir latência/timeout."""
    grupos: list[str] = []
    atual: list[str] = []
    tamanho_atual = 0

    for bloco in blocos:
        bloco = _limpar_bloco(bloco)
        if not bloco:
            continue

        excede_chars = tamanho_atual + len(bloco) > max_caracteres
        excede_paginas = len(atual) >= max_paginas_por_grupo
        if atual and (excede_chars or excede_paginas):
            grupos.append("\n\n".join(atual))
            atual = []
            tamanho_atual = 0

        atual.append(bloco)
        tamanho_atual += len(bloco)

    if atual:
        grupos.append("\n\n".join(atual))

    return grupos


def _selecionar_grupos_relevantes(
    grupos: list[str],
    doc: str,
    itens: list[ResultadoItem],
    *,
    limite_grupos: int = 3,
) -> list[str]:
    if not grupos:
        return []

    termos_doc = _DOUBLE_CHECK_TERMOS.get(doc, {})
    termos: list[str] = []
    for item in itens:
        termos.extend(termos_doc.get(item.item, []))
        termos.append(item.item)

    if not termos:
        return grupos[:limite_grupos]

    pontuados: list[tuple[int, int, str]] = []
    for idx, grupo in enumerate(grupos):
        texto = grupo.lower()
        score = sum(texto.count(termo.lower()) for termo in termos)
        pontuados.append((score, -idx, grupo))

    selecionados = [grupo for score, _, grupo in sorted(pontuados, reverse=True) if score > 0][:limite_grupos]
    if selecionados:
        return selecionados

    # Fallback seguro: começo, meio e fim dão contexto macro mesmo sem match literal.
    indices = sorted({0, len(grupos) // 2, len(grupos) - 1})
    return [grupos[i] for i in indices[:limite_grupos]]


def _descricao_double_check(
    observacao: str,
    evidencia: str | None = None,
) -> str:
    partes = [p.strip() for p in (observacao, evidencia) if p and p.strip()]
    return " Evidência: ".join(partes) if partes else (
        "Verificado pela IA — informação localizada no documento, em formato diverso do modelo atual."
    )


def _aplicar_revisao_double_check(
    item: ResultadoItem,
    revisao: dict | None,
) -> ResultadoItem:
    if not revisao:
        return item

    classificacao = (revisao.get("classificacao") or "").strip().upper()
    observacao = (revisao.get("observacao") or "").strip()
    evidencia = (revisao.get("evidencia") or "").strip()

    if classificacao == "AUSENTE":
        # Se a IA confirma que a informação está ausente, converte para INCONFORME
        return item.model_copy(update={
            "status": StatusRegra.INCONFORME,
            "descricao": _descricao_double_check(observacao or "Informação não localizada no documento.", evidencia),
            "via_ia": True,
            "providencia": Providencia.CORRIGIR,
        })

    if classificacao in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE:
        return item.model_copy(update={
            "status": StatusRegra.CONFORME,
            "descricao": _descricao_double_check(observacao, evidencia),
            "via_ia": True,
            "providencia": Providencia.PROSSEGUIR,
        })

    if classificacao == "PRESENTE_COM_RESSALVA":
        return item.model_copy(update={
            "descricao": _descricao_double_check(observacao, evidencia),
            "via_ia": True,
        })

    if classificacao == "NAO_FOI_POSSIVEL_AFERIR":
        # Mantém status original mas marca como revisado pela IA
        return item.model_copy(update={
            "descricao": f"{item.descricao} (IA: não foi possível aferir com o contexto disponível)",
            "via_ia": True,
        })

    return item


# ─────────────────────────────────────────────────────────────────────────────
# DFD
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_dfd(processo: ProcessoExtraido) -> list[ResultadoItem]:
    log.info("_analisar_dfd() chamado - DFD presente: %s, texto_original presente: %s", 
             bool(processo.dfd), bool(processo.dfd and processo.dfd.texto_original))
    
    dfd = processo.dfd
    if not dfd or not dfd.texto_original:
        log.warning("DFD ou texto_original ausente, retornando vazio")
        return []

    # Prepara contexto para análise de coerência DFD × TR
    contexto_dfd = dfd.texto_original
    if processo.tr and processo.tr.objeto:
        contexto_dfd += f"\n\nOBJETO DO TR:\n{processo.tr.objeto}"

    pergunta = """Analise o DFD (Documento de Formalização da Demanda) e avalie:

IMPORTANTE: Ignore erros de formatação, OCR ou digitação. Considere que o texto pode ter problemas de extração do PDF. Avalie APENAS o conteúdo substantivo.

1. "Objeto" – a descrição do objeto é específica e suficiente para identificar o que será contratado? (ignore erros de formatação/OCR)
2. "Justificativa PCA" – se a contratação não está prevista no PCA, a justificativa é plausível?
3. "Coerência Geral" – objeto, unidade, responsável e superior são coerentes entre si? (ignore erros de formatação/OCR)
4. "Coerência DFD × TR" – o objeto descrito no DFD é coerente com o objeto do Termo de Referência (TR)? VERIFIQUE RIGOROSAMENTE: 
   - O local/destinatário (cidade, promotoria, unidade) deve ser IGUAL em ambos os documentos. Se o DFD menciona uma cidade/promotoria e o TR menciona outra cidade/promotoria DIFERENTE, é INCONFORME.
   - A natureza da contratação deve ser consistente: se DFD menciona "confecção e instalação" (serviço) e TR menciona "aquisição" (compra), é INCONFORME.
   - O objeto principal deve ser o mesmo. Se os textos são muito diferentes e não descrevem a mesma essência da contratação, é INCONFORME.
   Considere que o DFD pode ser mais sucinto, mas deve descrever essencialmente a mesma contratação para o MESMO local/destinatário. Textos padronizados (declarações institucionais, observações padrão) não devem ser considerados como parte do núcleo descritivo do objeto.

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}

Omita itens que não se aplicam."""

    r = await analisar(pergunta, contexto_dfd, max_tokens=600)
    if not r:
        return []
    return [_de_avaliacao(_DOC_DFD, av) for av in r.get("avaliacoes", [])]


# ─────────────────────────────────────────────────────────────────────────────
# TR Serviços — extração estrutural + avaliação qualitativa
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_tr_servicos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tr = processo.tr
    if not isinstance(tr, TRServicosExtraido) or not tr.texto_original:
        return []

    # ── Chamada 1: campos estruturais (checkboxes) não extraídos pela regex ──
    estruturais: list[tuple[str, str]] = []  # (nome_item, instrucao)

    if not tr.objeto:
        estruturais.append(("1.1 – Objeto", "Descrição do objeto — conforme se clara e específica"))
    if not tr.fundamentacao:
        estruturais.append(("Fundamentação", "Há justificativa substantiva da contratação? — conforme se presente e não é texto de modelo"))
    if not tr.base_legal.artigo_inciso:
        estruturais.append(("2.1.1 – Artigo/Inciso", "Artigo/inciso da Lei 14.133/2021 — conforme se 'art. 75, inciso II'"))
    if not tr.divulgacao.opcao:
        estruturais.append(("2.1.2 – Divulgação", "Opção A (não publicar) ou B (publicar no Portal MPBA)? — conforme se B, ou A com justificativa"))
    if not tr.natureza_objeto:
        estruturais.append(("1.3 – Natureza do Objeto", "Opção A (não continuado), B (parcelado) ou C (continuado)? — conforme se qualquer opção assinalada"))
    if not tr.regime_execucao:
        estruturais.append(("3.1 – Regime de Execução", "Opção A (preço global), B (preço unitário) ou C (outro)? — conforme se qualquer opção assinalada"))
    if not tr.formalizacao_opcao:
        estruturais.append(("1.6/1.7 – Formalização", "Opção A (NE/substitutivo), B (contrato formal), C ou D (ATA)? — conforme SOMENTE se A; B/C/D = INCONFORME"))
    if not tr.responsavel_nome:
        estruturais.append(("Responsável / Assinatura", "Nome e assinatura do responsável — conforme se presente"))
    if not tr.prazo_execucao_dias:
        estruturais.append(("3.4 – Prazo de Execução", "Prazo de execução dos serviços — conforme se preenchido"))
    if not tr.garantia_opcao:
        estruturais.append(("3.5 – Garantia do Serviço", "Opção A-E assinalada? — conforme se qualquer opção; C/D exige justificativa"))
    if not tr.subcontratacao_opcao:
        estruturais.append(("3.6 – Subcontratação", "Opção A (vedada) ou B (admitida)? — conforme se qualquer opção assinalada"))
    if not tr.vigencia_opcao:
        estruturais.append(("3.13 – Vigência da Contratação", "Opção A ou B assinalada? — conforme se qualquer opção"))
    if not tr.garantia_contratual_opcao:
        estruturais.append(("3.16 – Garantia Contratual", "Opção A (não exigida) ou B (exigida ≤ 5%)? — conforme se qualquer opção"))
    estruturais.append((
        "3.7.4 – Multas",
        f"Percentuais de mora (%/dia) e inexecução total (%) — conforme se mora ≤ {_MORA_MAX}% E inexecução ≤ {_INEX_MAX}%; informe os valores na observação",
    ))

    itens_estruturais = "\n".join(
        f'{i+1}. "{nome}": {instr}'
        for i, (nome, instr) in enumerate(estruturais)
    )
    pergunta_est = (
        "Analise o Termo de Referência de SERVIÇOS (MPBA Jan/2026) e para CADA item abaixo "
        "indique se está conforme e uma observação em até 100 caracteres.\n\n"
        + itens_estruturais
        + "\n\nResponda APENAS com JSON (use EXATAMENTE os nomes entre aspas para 'item'):\n"
        '{"avaliacoes":[{"item":"...","conforme":true,"observacao":"..."}]}'
    )

    # ── Chamada 2: aspectos qualitativos ──────────────────────────────────────
    qualitativos: list[tuple[str, str]] = [
        ("Objeto (IA)", "A descrição do objeto é específica e adequada ao tipo de serviço? (ignore erros de formatação/OCR)"),
        ("Coerência Geral (IA)", "O TR está internamente consistente (objeto, regime, prazos e garantias coerentes)? (ignore erros de formatação/OCR)"),
    ]
    if tr.divulgacao.opcao == "A":
        qualitativos.append(("Divulgação – Justificativa (IA)", "A justificativa para não publicar no Portal MPBA é substantiva?"))
    if tr.habilitacao.tecnica_opcao == "B":
        qualitativos.append(("Habilitação Técnica (IA)", "Os requisitos técnicos exigidos são proporcionais e justificados?"))
    if tr.natureza_objeto and tr.natureza_objeto.upper() == "C":
        qualitativos.append(("Natureza Objeto – Justificativa (IA)", "A justificativa para serviço continuado (opção C) é adequada?"))

    itens_qual = "\n".join(
        f'{i+1}. "{nome}": {instr}'
        for i, (nome, instr) in enumerate(qualitativos)
    )
    pergunta_qual = (
        "Analise qualitativamente o Termo de Referência de SERVIÇOS (MPBA Jan/2026).\n\n"
        + itens_qual
        + "\n\nResponda APENAS com JSON:\n"
        '{"avaliacoes":[{"item":"...","conforme":true,"observacao":"..."}]}'
    )

    # Contexto estrutural: cabeçalho + seções onde ficam checkboxes + rodapé (assinatura)
    _SECS_EST = ["1.3", "1.6", "1.7", "2.1", "3.1", "3.4", "3.5", "3.6", "3.7", "3.13", "3.16"]
    ctx_est  = _fatiar_secoes(tr.texto_original, _SECS_EST)
    # Contexto qualitativo: apenas o cabeçalho (objeto + fundamentação)
    ctx_qual = tr.texto_original[:4000]

    r_est, r_qual = await asyncio.gather(
        analisar(pergunta_est, ctx_est,  max_tokens=1400),
        analisar(pergunta_qual, ctx_qual, max_tokens=800),
        return_exceptions=True,
    )

    resultados: list[ResultadoItem] = []
    for r in (r_est, r_qual):
        if isinstance(r, Exception) or not r:
            continue
        for av in r.get("avaliacoes", []):
            resultados.append(_de_avaliacao(_DOC_TR, av))
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# TR Aquisições — extração estrutural + avaliação qualitativa
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_tr_aquisicoes(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tr = processo.tr
    if not isinstance(tr, TRAquisicoesExtraido) or not tr.texto_original:
        return []

    estruturais: list[tuple[str, str]] = []

    if not tr.objeto:
        estruturais.append(("1.1 – Objeto", "Descrição do objeto — conforme se clara e específica"))
    if not tr.fundamentacao:
        estruturais.append(("Fundamentação", "Justificativa substantiva? — conforme se presente e não é texto de modelo"))
    if not tr.base_legal.artigo_inciso:
        estruturais.append(("2.1.1 – Artigo/Inciso", "Artigo/inciso Lei 14.133/2021 — conforme se 'art. 75, inciso II'"))
    if not tr.divulgacao.opcao:
        estruturais.append(("2.1.2 – Divulgação", "Opção A ou B? — conforme se B ou A com justificativa"))
    if not tr.natureza_objeto:
        estruturais.append(("1.4 – Natureza do Objeto", "Opção A (imediato), B (parcelado) ou C (continuado)? — conforme se assinalada"))
    if not tr.formalizacao_opcao:
        estruturais.append(("1.6/1.7 – Formalização", "Opção A (NE), B (contrato), C/D (ATA)? — conforme SOMENTE se A"))
    if not tr.responsavel_nome:
        estruturais.append(("Responsável / Assinatura", "Nome e assinatura — conforme se presente"))
    if not tr.garantia_opcao:
        estruturais.append(("3.6.1 – Garantia do Produto", "Opção A-E assinalada? — conforme se assinalada; C/D exige justificativa"))
    if not tr.subcontratacao_opcao:
        estruturais.append(("3.7 – Subcontratação", "Opção A (vedada) ou B (admitida)? — conforme se assinalada"))
    if not tr.vigencia_opcao:
        estruturais.append(("3.14 – Vigência da Contratação", "Opção A ou B? — conforme se assinalada"))
    estruturais.append((
        "3.9.4 – Multas",
        f"Mora (%/dia) e inexecução total (%) — conforme se mora ≤ {_MORA_MAX}% E inexecução ≤ {_INEX_MAX}%; informe os valores",
    ))

    itens_estruturais = "\n".join(
        f'{i+1}. "{nome}": {instr}'
        for i, (nome, instr) in enumerate(estruturais)
    )
    pergunta_est = (
        "Analise o Termo de Referência de AQUISIÇÕES (MPBA Jan/2026) e para CADA item "
        "indique se está conforme e uma observação em até 100 caracteres.\n\n"
        + itens_estruturais
        + "\n\nResponda APENAS com JSON (use EXATAMENTE os nomes entre aspas para 'item'):\n"
        '{"avaliacoes":[{"item":"...","conforme":true,"observacao":"..."}]}'
    )

    qualitativos: list[tuple[str, str]] = [
        ("Objeto (IA)", "A descrição do bem é específica e adequada? (ignore erros de formatação/OCR)"),
        ("Justificativa da Quantidade (IA)", "A quantidade está objetivamente justificada?"),
        ("Coerência Geral (IA)", "O TR está internamente consistente? (ignore erros de formatação/OCR)"),
    ]
    if tr.marca_modelo_opcao and tr.marca_modelo_opcao.upper() in ("B", "C"):
        qualitativos.append(("Marca/Modelo – Justificativa (IA)", "A justificativa para marca/modelo é técnica e não preferencial?"))
    if tr.natureza_objeto and tr.natureza_objeto.upper() == "C":
        qualitativos.append(("Natureza Objeto – Justificativa (IA)", "Justificativa para fornecimento continuado é adequada?"))

    itens_qual = "\n".join(f'{i+1}. "{nome}": {instr}' for i, (nome, instr) in enumerate(qualitativos))
    pergunta_qual = (
        "Analise qualitativamente o TR de AQUISIÇÕES (MPBA Jan/2026).\n\n"
        + itens_qual
        + "\n\nResponda APENAS com JSON:\n"
        '{"avaliacoes":[{"item":"...","conforme":true,"observacao":"..."}]}'
    )

    _SECS_EST = ["1.4", "1.6", "1.7", "2.1", "3.1", "3.6", "3.7", "3.9", "3.14"]
    ctx_est  = _fatiar_secoes(tr.texto_original, _SECS_EST)
    ctx_qual = tr.texto_original[:4000]

    r_est, r_qual = await asyncio.gather(
        analisar(pergunta_est, ctx_est,  max_tokens=1400),
        analisar(pergunta_qual, ctx_qual, max_tokens=800),
        return_exceptions=True,
    )

    resultados: list[ResultadoItem] = []
    for r in (r_est, r_qual):
        if isinstance(r, Exception) or not r:
            continue
        for av in r.get("avaliacoes", []):
            resultados.append(_de_avaliacao(_DOC_TR, av))
    return resultados


# ─────────────────────────────────────────────────────────────────────────────
# Tabela de Preços Orçados
# ─────────────────────────────────────────────────────────────────────────────

async def _analisar_tabela_precos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    tp = processo.tabela_precos
    if not tp:
        return []

    ctx_parts = []
    # Objeto da contratação — vem do TR; fallback para descrição_solucao
    objeto_tr = None
    if processo.tr:
        objeto_tr = processo.tr.objeto or getattr(processo.tr, "descricao_solucao", None)
    if objeto_tr:
        ctx_parts.append(f"Objeto da contratação: {objeto_tr[:200]}")
    if tp.motivacao_fornecedores:
        ctx_parts.append(f"Motivação para escolha dos fornecedores: {tp.motivacao_fornecedores}")
    if tp.metodologia_menor_preco is not None:
        ctx_parts.append(f"Metodologia menor preço: {'Sim' if tp.metodologia_menor_preco else 'Não identificada'}")
    if tp.responsavel_nome:
        ctx_parts.append(f"Responsável: {tp.responsavel_nome}")
    if not ctx_parts:
        return []

    contexto = "\n".join(ctx_parts)

    pergunta = """Analise os dados da Tabela de Preços Orçados e avalie:

1. "Motivação dos Fornecedores" – a justificativa para escolha dos fornecedores é objetiva (não é genérica como 'empresas do ramo')?

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}

Omita itens sem informação suficiente."""

    r = await analisar(pergunta, contexto, max_tokens=400)
    if not r:
        return []
    return [_de_avaliacao(_DOC_PRECOS, av) for av in r.get("avaliacoes", [])]




# ─────────────────────────────────────────────────────────────────────────────
# Orçamentos / Propostas
# ---------------------------------------------------------------------

async def _analisar_orcamentos(processo: ProcessoExtraido) -> list[ResultadoItem]:
    if not processo.orcamentos or not processo.tr:
        return []

    objeto = processo.tr.objeto or ""
    valores = [
        f"  - {o.razao_social or 'Empresa ' + str(i)}: R$ {o.valor_total:,.2f}"
        for i, o in enumerate(processo.orcamentos, 1)
        if o.valor_total
    ]
    if not valores or not objeto:
        return []

    contexto = f"Objeto da contratação: {objeto}\n\nValores propostos:\n" + "\n".join(valores)

    pergunta = """Avalie as propostas:

1. "Compatibilidade Valores × Objeto" - os valores propostos são compatíveis com o mercado para o objeto descrito?
2. "Variação entre Propostas" - a variação entre propostas é razoável (sem valores idênticos suspeitos ou discrepância extrema)?

Responda APENAS com JSON:
{"avaliacoes": [{"item": "...", "conforme": true/false, "observacao": "..."}]}"""

    r = await analisar(pergunta, contexto, max_tokens=400)
    if not r:
        return []
    return [_de_avaliacao(_DOC_ORC, av) for av in r.get("avaliacoes", [])]


# ---------------------------------------------------------------------
# Orquestrador
# ─────────────────────────────────────────────────────────────────────────────

# Itens determinísticos que a IA pode substituir quando resolvê-los.
# A IA devolve o item com o MESMO nome → remove o determinístico correspondente.
_ITENS_IA_SUBSTITUI = {
    # TR Serviços e Aquisições – campos estruturais (ex-PENDÊNCIA/INCONFORME)
    "1.1 – Objeto",
    "Fundamentação",
    "2.1.1 – Artigo/Inciso",
    "2.1.2 – Divulgação",
    "1.3 – Natureza do Objeto",
    "1.4 – Natureza do Objeto",
    "3.1 – Regime de Execução",
    "1.6/1.7 – Formalização",
    "Responsável / Assinatura",
    "3.4 – Prazo de Execução",
    "3.5 – Garantia do Serviço",
    "3.6 – Subcontratação",
    "3.7 – Subcontratação",
    "3.6.1 – Garantia do Produto",
    "3.13 – Vigência da Contratação",
    "3.14 – Vigência da Contratação",
    "3.16 – Garantia Contratual",
    "3.7.4 – Multas",
    "3.9.4 – Multas",
    # DFD
    "Objeto",
}

_ITENS_IA_SUBSTITUI_NORM: dict[str, str] = {
    normalizar_rotulo_regra(n): n for n in _ITENS_IA_SUBSTITUI
}


def _canon_item_substituivel(nome: str) -> str | None:
    """Nome canônico em ``_ITENS_IA_SUBSTITUI`` quando a IA varia traços ou espaços."""
    return _ITENS_IA_SUBSTITUI_NORM.get(normalizar_rotulo_regra(nome))


def _chave_revisao_double_check(documento: str, item: str) -> tuple[str, str]:
    return (normalizar_rotulo_regra(documento), normalizar_rotulo_regra(item))


async def aplicar_regras_ia(
    processo: ProcessoExtraido,
    resultados_deterministicos: list[ResultadoItem],
) -> tuple[list[ResultadoItem], list[ResultadoItem]]:
    """Executa todas as análises de IA em paralelo.

    Retorna (deterministicos_filtrados, novos_ia):
    - Itens que a IA resolve (nome exato em _ITENS_IA_SUBSTITUI): remove o determinístico
      e usa o resultado da IA no lugar.
    - Itens qualitativos (sufixo ' (IA)'): adicionados como itens extras.
    """
    tarefas = [
        _analisar_dfd(processo),
        _analisar_tr_servicos(processo),
        _analisar_tr_aquisicoes(processo),
        _analisar_tabela_precos(processo),
        _analisar_orcamentos(processo),
    ]

    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    novos: list[ResultadoItem] = []
    itens_resolvidos_pela_ia: set[tuple[str, str]] = set()  # (documento, item)

    for res in resultados:
        if isinstance(res, Exception):
            log.warning("Tarefa IA falhou: %s", res)
            continue
        for item in res:
            canon = _canon_item_substituivel(item.item)
            if canon:
                item = item.model_copy(update={"item": canon})
            novos.append(item)
            # Registra itens que a IA resolveu (nome exato, sem sufixo " (IA)")
            if canon:
                itens_resolvidos_pela_ia.add((item.documento, canon))
                log.debug("IA resolveu: [%s] %s → %s", item.documento, canon, item.status.value)

    # Remove dos determinísticos os itens que a IA substituiu
    deterministicos = [
        r for r in resultados_deterministicos
        if (r.documento, r.item) not in itens_resolvidos_pela_ia
    ]

    removidos = len(resultados_deterministicos) - len(deterministicos)
    if removidos:
        log.info("IA substituiu %d item(ns) determinístico(s).", removidos)

    return deterministicos, novos


# ─────────────────────────────────────────────────────────────────────────────
# Double-check: IA confirma ou descarta cada INCONFORME / PENDÊNCIA
# ─────────────────────────────────────────────────────────────────────────────

def _contexto_double_check(
    processo: ProcessoExtraido,
    doc: str,
    itens: list[ResultadoItem],
) -> str:
    """Retorna o melhor contexto disponível para o documento pedido."""
    if doc == _DOC_DFD and processo.dfd and processo.dfd.texto_original:
        grupos = _agrupar_blocos_texto(processo.dfd.blocos_texto or [processo.dfd.texto_original])
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_TR and processo.tr and processo.tr.texto_original:
        grupos = _agrupar_blocos_texto(processo.tr.blocos_texto or [processo.tr.texto_original])
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_PRECOS and processo.tabela_precos:
        tp = processo.tabela_precos
        partes: list[str] = tp.blocos_texto[:] if tp.blocos_texto else []
        if tp.aviso_previo_publicado is not None:
            partes.append(f"Aviso prévio publicado: {'Sim' if tp.aviso_previo_publicado else 'Não identificado'}")
        if tp.propostas_recebidas is not None:
            partes.append(f"Propostas recebidas: {tp.propostas_recebidas}")
        if tp.data_orcamento:
            partes.append(f"Data do orçamento: {tp.data_orcamento}")
        if tp.motivacao_fornecedores:
            partes.append(f"Motivação fornecedores: {tp.motivacao_fornecedores[:300]}")
        grupos = _agrupar_blocos_texto(partes)
        selecionados = _selecionar_grupos_relevantes(grupos, doc, itens)
        return _montar_contexto_double_check("\n\n".join(selecionados), doc, itens)

    if doc == _DOC_ORC and processo.orcamentos:
        linhas = [f"Orçamentos encontrados: {len(processo.orcamentos)}"]
        for i, o in enumerate(processo.orcamentos, 1):
            val = f"R$ {o.valor_total:,.2f}" if o.valor_total else "valor não extraído"
            linhas.append(f"  {i}. {o.razao_social or '?'} – CNPJ: {o.cnpj_cpf or '?'} – {val} – data: {o.data_proposta or '?'}")
        return _montar_contexto_double_check("\n".join(linhas), doc, itens)

    if doc == "Certidões" and processo.certidoes:
        return _montar_contexto_double_check(
            json.dumps(processo.certidoes.model_dump(), ensure_ascii=False, default=str),
            doc,
            itens,
        )

    return ""


async def _double_check_doc(
    doc: str,
    itens: list[ResultadoItem],
    contexto: str,
) -> list[dict]:
    """Envia um lote de itens (CONFORME, INCONFORME, PENDÊNCIA) à IA para validação contextual."""
    hoje = date.today().strftime("%d/%m/%Y")
    lista = "\n".join(
        f'{i+1}. "{it.item}" ({it.status.value}): {it.descricao}'
        for i, it in enumerate(itens)
    )
    pergunta = (
        f"Data de hoje: {hoje}.\n"
        f"Você é revisor de saneamento de Dispensa de Licitação (MPBA/Lei 14.133/2021).\n"
        f"O sistema automático classificou os itens abaixo no documento '{doc}'.\n"
        f"Analise o contexto fornecido e faça uma validação refinada de TODOS os itens.\n"
        f"Considere explicitamente que o documento pode seguir MODELO ANTIGO, com outra nomenclatura, "
        f"ordem de seções, redação ou formatação. O foco é verificar se a informação material exigida "
        f"está presente, ainda que em formato diferente do template atual.\n\n"
        f"Classifique cada item usando UMA destas opções:\n"
        f"- AUSENTE: a informação realmente não aparece no documento.\n"
        f"- PRESENTE_VARIACAO_FORMA: a informação está presente, mas em seção/título/formato diverso.\n"
        f"- PRESENTE_EQUIVALENTE: a informação exigida está claramente presente e adequada.\n"
        f"- PRESENTE_COM_RESSALVA: a informação aparece de forma substantiva, mas há insuficiência, "
        f"inconsistência ou dúvida relevante sobre o conteúdo. "
        f"NÃO use esta opção para: artefatos de OCR, texto ilegível/corrompido, "
        f"placeholder de modelo não preenchido (ex.: '[inserir...]', 'xx dias'), "
        f"ou endereço de e-mail com espaço/caractere inválido onde deveria haver '@'.\n"
        f"- NAO_FOI_POSSIVEL_AFERIR: o contexto não permite concluir com segurança.\n\n"
        f"REGRA EXTRA — campos de e-mail: só classifique como PRESENTE_* se houver endereço "
        f"completo e válido (formato usuario@dominio) no texto. Texto garbled ou sem '@' = AUSENTE.\n\n"
        f"Itens para validação:\n{lista}\n\n"
        f"Responda APENAS com JSON — use EXATAMENTE os nomes entre aspas para 'item':\n"
        '{"revisoes":[{"item":"...","classificacao":"AUSENTE|PRESENTE_VARIACAO_FORMA|PRESENTE_EQUIVALENTE|PRESENTE_COM_RESSALVA|NAO_FOI_POSSIVEL_AFERIR","observacao":"...","evidencia":"trecho curto ou referência textual"}]}'
    )
    r = await analisar(pergunta, contexto, max_tokens=800)
    if not r:
        return []
    return [
        {
            "documento": doc,
            "item": rv.get("item", ""),
            "classificacao": rv.get("classificacao", ""),
            "observacao": rv.get("observacao", ""),
            "evidencia": rv.get("evidencia", ""),
        }
        for rv in r.get("revisoes", [])
    ]


async def double_check_inconformidades(
    processo: ProcessoExtraido,
    todos: list[ResultadoItem],
) -> list[ResultadoItem]:
    """Double-check via IA de todos os itens (CONFORME, INCONFORME, PENDÊNCIA) de TR e DFD antes do relatório final.

    Para TR e DFD, todos os status passam pela IA para validação refinada.
    Para outros documentos, apenas INCONFORME/PENDÊNCIA são revisados.
    Quando a IA identifica que a informação exigida está presente em formato
    equivalente ou em modelo antigo, o item é convertido em CONFORME com
    ``via_ia=True`` para rastreabilidade.
    """
    # Para TR e DFD, inclui todos os itens (CONFORME, INCONFORME, PENDÊNCIA)
    # Para outros documentos, apenas INCONFORME/PENDÊNCIA
    problemas = [
        r for r in todos 
        if r.documento in (_DOC_TR, _DOC_DFD) 
        or r.status in (StatusRegra.INCONFORME, StatusRegra.PENDENCIA)
    ]
    if not problemas:
        return todos

    # Agrupa por documento e monta contextos
    por_doc: dict[str, list[ResultadoItem]] = {}
    for item in problemas:
        por_doc.setdefault(item.documento, []).append(item)

    tarefas: list = []
    for doc, itens in por_doc.items():
        for lote in _iterar_lotes(itens, _DOUBLE_CHECK_MAX_ITENS_POR_LOTE):
            ctx = _contexto_double_check(processo, doc, lote)
            if not ctx:
                continue
            tarefas.append(_double_check_doc(doc, lote, ctx))

    if not tarefas:
        return todos

    resultados = await asyncio.gather(*tarefas, return_exceptions=True)

    revisoes_por_item: dict[tuple[str, str], dict] = {}

    for res in resultados:
        if isinstance(res, Exception) or not res:
            continue
        for rv in res:
            key = _chave_revisao_double_check(str(rv.get("documento", "")), str(rv.get("item", "")))
            revisoes_por_item[key] = rv
            if rv.get("classificacao") in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE:
                log.info(
                    "Double-check: informação confirmada por IA em formato equivalente – [%s] %s",
                    rv["documento"],
                    rv["item"],
                )

    log.info("Double-check IA: %d item(ns) reclassificado(s) como presentes de %d revisado(s).",
             sum(
                 1
                 for rv in revisoes_por_item.values()
                 if rv.get("classificacao") in _DOUBLE_CHECK_CLASSIFICACOES_PRESENTE
             ),
             len(problemas))

    resultado_final: list[ResultadoItem] = []
    for item in todos:
        key = _chave_revisao_double_check(item.documento, item.item)
        resultado_final.append(_aplicar_revisao_double_check(item, revisoes_por_item.get(key)))

    return resultado_final
